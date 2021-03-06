/****************************************************************/
/* MOOSE - Multiphysics Object Oriented Simulation Environment  */
/*                                                              */
/*          All contents are licensed under LGPL V2.1           */
/*             See LICENSE for full restrictions                */
/****************************************************************/
#include "HomogenizationHeatConduction.h"

template<>
InputParameters validParams<HomogenizationHeatConduction>()
{
  InputParameters params = validParams<Kernel>();
  params.addParam<MaterialPropertyName>("diffusion_coefficient_name","thermal_conductivity", "The diffusion coefficient for the temperature gradient (Default: thermal_conductivity)");
  params.addRequiredParam<unsigned int>("component", "An integer corresponding to the direction the variable this kernel acts in. (0 for x, 1 for y, 2 for z)");

  return params;
}


HomogenizationHeatConduction::HomogenizationHeatConduction(const std::string & name, InputParameters parameters)
  :Kernel(name, parameters),
   _diffusion_coefficient(getMaterialProperty<Real>("diffusion_coefficient_name")),
   _component(getParam<unsigned int>("component"))
{}

Real
HomogenizationHeatConduction::computeQpResidual()
{
  // Compute positive value since we are computing a residual not a rhs
  return _diffusion_coefficient[_qp] * _grad_test[_i][_qp](_component);
}
