#! /bin/bash

TRIGGER_TIME=1137215767.988

MASS1=1.4
MASS2=1.4
SPIN1Z=0
SPIN2Z=0

TRIGGER_TIME_INT=${TRIGGER_TIME%.*}

GPS_START_TIME=$((${TRIGGER_TIME_INT} - 1024))
GPS_END_TIME=$((${TRIGGER_TIME_INT} + 1024))

CHANNEL_NAME=H1:DCS-CALIB_STRAIN_C02
FRAME_TYPE=H1:H1_HOFT_C02

pycbc_mcmc --verbose \
    --instruments H1 \
    --gps-start-time ${GPS_START_TIME} \
    --gps-end-time ${GPS_END_TIME} \
    --frame-type ${FRAME_TYPE} \
    --channel-name ${CHANNEL_NAME} \
    --sample-rate 2048 \
    --low-frequency-cutoff 40 \
    --strain-high-pass 30 \
    --pad-data 8 \
    --psd-estimation median \
    --psd-segment-length 16 \
    --psd-segment-stride 8 \
    --psd-inverse-length 16 \
    --processing-scheme mkl \
    --sampler kombine \
    --likelihood-evaluator gaussian \
    --nwalkers 8 \
    --niterations 1000 \
    --approximant TaylorF2 \
    --variable-args tc mass1 mass2 \
    --prior-min 1024.92 1.30 1.30 \
    --prior-max 1025.04 10.00 10.00 \
    --prior-dist flat flat flat \
    --ra 0.0247836709 \
    --dec 0.00715585006 \
    --polarization 2.56616092 \
    --f-lower 40.0 \
    --output-file test_cli.hdf



