/****************************************************************/
/* MOOSE - Multiphysics Object Oriented Simulation Environment  */
/*                                                              */
/*          All contents are licensed under LGPL V2.1           */
/*             See LICENSE for full restrictions                */
/****************************************************************/
#include "ComputePolycrystalElasticityTensor.h"
#include "AddV.h"
#include "RotationTensor.h"
#include "GrainTracker.h"
#include "Conversion.h"

template<>
InputParameters validParams<ComputePolycrystalElasticityTensor>()
{
  InputParameters params = validParams<ComputeElasticityTensorBase>();
  params.addClassDescription("Compute an evolving elasticity tensor coupled to a grain growth phase field model.");
  params.addRequiredParam<FileName>("Euler_angles_file_name", "Name of the file containing the Euler angles");
  params.addParam<Real>("length_scale", 1.0e-9, "Lengthscale of the problem, in meters");
  params.addParam<Real>("pressure_scale", 1.0e6, "Pressure scale of the problem, in pa");
  params.addRequiredParam<unsigned int>("op_num", "number of order parameters");
  params.addRequiredParam<std::string>("var_name_base", "base for variable names");
  params.addCoupledVar("v", "Array of coupled variables");
  params.addRequiredParam<UserObjectName>("GrainTracker_object", "The GrainTracker UserObject to get values from.");
  params.addRequiredParam<unsigned int>("grain_num", "Number of initial grains that will be modeled");
  params.addParam<unsigned int>("stiffness_buffer",10,"Number of extra elastic stiffnesses that are created to handle new grains");
  params.addRequiredParam<std::vector<Real> >("Elastic_constants", "Vector containing elastic constants for fill method");
  params.addParam<MooseEnum>("fill_method", RankFourTensor::fillMethodEnum() = "symmetric9", "The fill method");
  return params;
}

ComputePolycrystalElasticityTensor::ComputePolycrystalElasticityTensor(const std::string & name,
                                                 InputParameters parameters) :
    ComputeElasticityTensorBase(name, AddV(parameters) ),
    _C_unrotated(getParam<std::vector<Real> >("Elastic_constants"), (RankFourTensor::FillMethod)(int)getParam<MooseEnum>("fill_method")),
    _length_scale(getParam<Real>("length_scale")),
    _pressure_scale(getParam<Real>("pressure_scale")),
    _Euler_angles_file_name(getParam<FileName>("Euler_angles_file_name")),
    _grain_tracker(getUserObject<GrainTracker>("GrainTracker_object")),
    _grain_num(getParam<unsigned int>("grain_num")),
    _stiffness_buffer(getParam<unsigned int>("stiffness_buffer")),
    _JtoeV(6.24150974e18), // Joule to eV conversion
    _nop(coupledComponents("v"))
{
  // Initialize values for crystals
  _vals.resize(_nop);
  _D_elastic_tensor.resize(_nop);
  _C_rotated.resize(_grain_num + _stiffness_buffer);

  // Read in Euler angles from "angle_file_name"
  std::ifstream inFile(_Euler_angles_file_name.c_str());

  if (!inFile)
    mooseError("Can't open " + _Euler_angles_file_name);

  for (unsigned int i = 0; i < 4; ++i)
    inFile.ignore(std::numeric_limits<std::streamsize>::max(), '\n'); // ignore line

  Real weight;

  // Loop over grains
  for (unsigned int grn = 0; grn < _grain_num; ++grn)
  {
    // Read in Euler angles
    RealVectorValue Euler_Angles;
    for (unsigned int j=0; j<3; ++j)
      inFile >> Euler_Angles(j);

    // Read in weight
    inFile >> weight;

    // Rotate one elasticity tensor for each grain
    RotationTensor R(Euler_Angles);
    _C_rotated[grn] = _C_unrotated;
    _C_rotated[grn].rotate(R);

    if (grn < _stiffness_buffer)
    {
      _C_rotated[grn + _grain_num] = _C_unrotated;
      _C_rotated[grn + _grain_num].rotate(R);
    }
  }

  // Close Euler angle file
  inFile.close();

  // Loop over variables (ops)
  for (unsigned int op = 0; op < _nop; ++op)
  {
    // Initialize variables
    _vals[op] = &coupledValue("v", op);

    // Create variable name
    std::string var_name = getParam<std::string>("var_name_base") + Moose::stringify(op);

    // Create names of derivative properties of elasticity tensor
    std::string material_name = propertyNameFirst(_elasticity_tensor_name, var_name);

    // declare elasticity tensor derivative properties
    _D_elastic_tensor[op] = &declareProperty<ElasticityTensorR4>(material_name);
  }
}

void
ComputePolycrystalElasticityTensor::computeQpElasticityTensor()
{
  // Initialize local elasticity tnesor and sum of h
  ElasticityTensorR4 local_elasticity_tensor;

  Real sum_h = 0.0;

  // Get list of active order parameters from grain tracker
  const std::vector<std::pair<unsigned int, unsigned int> > & active_ops = _grain_tracker.getElementalValues(_current_elem->id());

  unsigned int n_active_ops= active_ops.size();

  if (n_active_ops < 1 && _t_step > 0 )
    mooseError("No active order parameters");

  // Calculate elasticity tensor
  for (unsigned int op = 0; op<n_active_ops; ++op)
  {
    // First position of the active ops contains grain number (starting at 1)
    unsigned int grn_index = active_ops[op].first - 1;

    // Second position contains the order parameter index
    unsigned int op_index = active_ops[op].second;

    // Interpolation factor for elasticity tensors
    Real h = (1.0 + std::sin(libMesh::pi * ((*_vals[op_index])[_qp] - 0.5)))/2.0;

    // Sum all rotated elasticity tensors
    local_elasticity_tensor += _C_rotated[grn_index]*h;
    sum_h += h;
  }

  Real tol = 1.0e-10;
  if (sum_h < tol)
    sum_h = tol;

  local_elasticity_tensor /= sum_h;

  // Fill in the matrix stiffness material property
  _elasticity_tensor[_qp] = local_elasticity_tensor;

  // Calculate elasticity tensor derivative: Cderiv = dhdopi/sum_h * (Cop - _Cijkl)
  for (unsigned int op = 0; op < _nop; ++op)
    (*_D_elastic_tensor[op])[_qp].zero();

  for (unsigned int op = 0; op < n_active_ops; ++op)
  {
    unsigned int grn_index = active_ops[op].first - 1;
    unsigned int op_index = active_ops[op].second;
    Real dhdopi = libMesh::pi * std::cos(libMesh::pi * ((*_vals[op_index])[_qp] - 0.5))/2.0;
    ElasticityTensorR4 C_deriv(_C_rotated[grn_index]);
    C_deriv -= local_elasticity_tensor;
    C_deriv *= dhdopi/sum_h;

    // Convert from XPa to eV/(xm)^3, where X is pressure scale and x is length scale;
    C_deriv *= _JtoeV * (_length_scale * _length_scale * _length_scale) * _pressure_scale;

    // Fill in material property
    (*_D_elastic_tensor[op_index])[_qp] = C_deriv;
  }
}
