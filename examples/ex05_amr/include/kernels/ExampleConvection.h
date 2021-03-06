/****************************************************************/
/*               DO NOT MODIFY THIS HEADER                      */
/* MOOSE - Multiphysics Object Oriented Simulation Environment  */
/*                                                              */
/*           (c) 2010 Battelle Energy Alliance, LLC             */
/*                   ALL RIGHTS RESERVED                        */
/*                                                              */
/*          Prepared by Battelle Energy Alliance, LLC           */
/*            Under Contract No. DE-AC07-05ID14517              */
/*            With the U. S. Department of Energy               */
/*                                                              */
/*            See COPYRIGHT for full restrictions               */
/****************************************************************/

#ifndef EXAMPLECONVECTION_H
#define EXAMPLECONVECTION_H

#include "Kernel.h"

class ExampleConvection;

template<>
InputParameters validParams<ExampleConvection>();

class ExampleConvection : public Kernel
{
public:

  ExampleConvection(const std::string & name,
                    InputParameters parameters);

protected:

  virtual Real computeQpResidual();

  virtual Real computeQpJacobian();

private:

  VariableGradient & _some_variable;
};

#endif //EXAMPLECONVECTION_H
