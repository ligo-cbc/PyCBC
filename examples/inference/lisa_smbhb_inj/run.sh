#!/bin/sh
pycbc_inference \
--config-files `dirname "$0"`/lisa_smbhb_relbin.ini \
--output-file lisa_smbhb_inj_pe.hdf \
--force \
--verbose
