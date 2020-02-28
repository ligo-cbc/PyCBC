#!/bin/sh
for f in emcee_stub.ini emcee_pt_stub.ini dynesty_stub.ini ultranest_stub.ini epsie_stub.ini; do
        echo $f
	pycbc_inference --verbose \
        --config-files simp.ini $f \
        --output-file $f.hdf \
        --nprocesses 2 \
        --seed 10 \
        --verbose \
        --force
done

pycbc_inference_plot_posterior --input-file \
emcee_stub.ini.hdf:emcee \
emcee_pt_stub.ini.hdf:emcee_pt \
dynesty_stub.ini.hdf:dynesty \
ultranest_stub.ini.hdf:ultranest \
epsie_stub.ini.hdf:espie \
--output-file sample.png
