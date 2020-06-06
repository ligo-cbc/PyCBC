#!/bin/bash

# example/test of running PyCBC Live on simulated data

set -e

export OMP_NUM_THREADS=4
export HDF5_USE_FILE_LOCKING="FALSE"

gps_start_time=1272790000
gps_end_time=1272790500

# test if there is a template bank. If not, make one

if [[ ! -f template_bank.hdf ]]
then
    echo -e "\\n\\n>> [`date`] Making template bank"
    curl \
        --remote-name \
        --silent \
        --show-error \
        https://raw.githubusercontent.com/gwastro/pycbc-config/710dbfd3590bd93d7679d7822da59fcb6b6fac0f/O2/bank/H1L1-HYPERBANK_SEOBNRv4v2_VARFLOW_THORNE-1163174417-604800.xml.gz

    pycbc_coinc_bank2hdf \
        --bank-file H1L1-HYPERBANK_SEOBNRv4v2_VARFLOW_THORNE-1163174417-604800.xml.gz \
        --output-file template_bank_full.hdf

    rm -f H1L1-HYPERBANK_SEOBNRv4v2_VARFLOW_THORNE-1163174417-604800.xml.gz

    pycbc_hdf5_splitbank \
        --bank-file template_bank_full.hdf \
        --output-prefix template_bank_ \
        --random-sort \
        --random-seed 831486 \
        --templates-per-bank 50

    mv template_bank_0.hdf template_bank.hdf
    rm -f template_bank_*.hdf
fi

# test if there is a hwinj file. If not, make one.

if [[ -f hwinjcbc*.xml.gz ]]
then    
    inj_names=`ls ./hwinjcbc*.xml.gz`
    if ${inj_name[@]} > 1
        then echo -e "\\n\\n>> [`date`] Too many injection xmls, only first will be used"
else
    echo -e "\\n\\n>> [`date`] Generating injection"
    
    inj_snr=30
    inj_time=1272790440
    inj_mass1=7.2797217
    inj_mass2=6.9102380
    inj_spin1z=0.7189988
    inj_spin2z=0.1991984
    
    pycbc_generate_hwinj \
        --network-snr $inj_snr \
        --ra 45.0 \
        --dec 45.0 \
        --polarization 0.0 \
        --approximant SEOBNRv4 \
        --mass1 $inj_mass1 \
        --mass2 $inj_mass2 \
        --spin1z $inj_spin1z \
        --spin2z $inj_spin2z \
        --inclination 0.0 \
        --taper TAPER_START \
        --waveform-low-frequency-cutoff 10 \
        --geocentric-end-time 1272790440 \
        --instruments H1 L1 V1 \
        --low-frequency-cutoff 10 \
        --sample-rate H1:16384 L1:16384 V1:16384 \
        --gps-end-time 1272790500 \
        --gps-start-time 1272790000 \
        --psd-model H1:aLIGOMidLowSensitivityP1200087 L1:aLIGOMidLowSensitivityP1200087 V1:AdVEarlyLowSensitivityP1200087
    inj_names=`ls ./hwinjcbc*.xml.gz`    
fi

inj_file=${inj_names[0]} 

# test if strain files exist. If they dont, make them

if [[ ! -d ./strain ]]
then        
    echo -e "\\n\\n>> [`date`] Generating simulated strain"
    
    function simulate_strain { # detector PSD_model random_seed
        mkdir -p strain/$1
        pycbc_condition_strain \
            --fake-strain $2 \
            --fake-strain-seed $3 \
            --output-strain-file "strain/$1/$1-SIMULATED_STRAIN-{start}-{duration}.gwf" \
            --gps-start-time $gps_start_time \
            --gps-end-time $gps_end_time \
            --sample-rate 16384 \
            --low-frequency-cutoff 10 \
            --channel-name $1:SIMULATED_STRAIN \
            --frame-duration 32 \
            --injection-file $inj_file
    }
    simulate_strain H1 aLIGOMidLowSensitivityP1200087 1234
    simulate_strain L1 aLIGOMidLowSensitivityP1200087 2345
    simulate_strain V1 AdVEarlyLowSensitivityP1200087 3456
fi


echo -e "\\n\\n>> [`date`] Running PyCBC Live"

mpirun \
-host localhost,localhost \
-n 2 \
-x PYTHONPATH -x LD_LIBRARY_PATH -x OMP_NUM_THREADS -x VIRTUAL_ENV -x PATH -x HDF5_USE_FILE_LOCKING \
\
python -m mpi4py `which pycbc_live` \
--bank-file template_bank.hdf \
--sample-rate 2048 \
--enable-bank-start-frequency \
--low-frequency-cutoff 18 \
--max-length 256 \
--approximant "SPAtmplt:mtotal<4" "SEOBNRv4_ROM:else" \
--chisq-bins "0.72*get_freq('fSEOBNRv4Peak',params.mass1,params.mass2,params.spin1z,params.spin2z)**0.7" \
--snr-abort-threshold 500 \
--snr-threshold 4.5 \
--newsnr-threshold 4.5 \
--max-triggers-in-batch 30 \
--store-loudest-index 50 \
--analysis-chunk 8 \
--autogating-threshold 50 \
--autogating-pad 0.5 \
--autogating-cluster 1 \
--autogating-width 0.25 \
--autogating-taper 0.25 \
--highpass-frequency 13 \
--highpass-bandwidth 5 \
--highpass-reduction 200 \
--psd-samples 30 \
--max-psd-abort-distance 600 \
--min-psd-abort-distance 20 \
--psd-abort-difference .15 \
--psd-recalculate-difference .01 \
--psd-inverse-length 3.5 \
--psd-segment-length 4 \
--trim-padding .5 \
--store-psd \
--increment-update-cache \
    H1:strain/H1 \
    L1:strain/L1 \
    V1:strain/V1 \
--frame-src \
    H1:strain/H1/* \
    L1:strain/L1/* \
    V1:strain/V1/* \
--frame-read-timeout 100 \
--channel-name \
    H1:SIMULATED_STRAIN \
    L1:SIMULATED_STRAIN \
    V1:SIMULATED_STRAIN \
--processing-scheme cpu:4 \
--fftw-measure-level 0 \
--fftw-threads-backend openmp \
--increment 8 \
--max-batch-size 16777216 \
--output-path output \
--day-hour-output-prefix \
--background-statistic newsnr_sgveto \
--sgchisq-snr-threshold 4 \
--sgchisq-locations "mtotal>40:20-30,20-45,20-60,20-75,20-90,20-105,20-120" \
--enable-background-estimation \
--background-ifar-limit 100 \
--timeslide-interval 0.1 \
--pvalue-combination-livetime 0.0005 \
--ifar-double-followup-threshold 0.0001 \
--ifar-upload-threshold 0.0001 \
--round-start-time 4 \
--start-time $gps_start_time \
--end-time $gps_end_time

echo -e "\\n\\n>> [`date`] Checking results"
python ./check_results.py
