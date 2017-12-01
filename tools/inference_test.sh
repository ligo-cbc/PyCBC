#!/bin/bash

# Calcualate a quick analytic likelihood parameter estimation
cat > ana_inf.ini <<EOL
[variable_args]
x =
y =

[prior-x]
name = uniform
min-x = -10
max-x = 10

[prior-y]
name = uniform
min-y = -10
max-y = 10
EOL

RESULT=`pycbc_inference --verbose \
    --config-files ana_inf.ini \
    --output-file ana_inf.hdf \
    --sampler emcee \
    --niterations 100 \
    --nwalkers 500 \
    --likelihood-evaluator test_normal`

if test $? -ne 0 ; then
    RESULT=1
    echo -e "    FAILED!"
    echo -e "---------------------------------------------------------"
else
    echo -e "    Pass."
fi

exit ${RESULT}
