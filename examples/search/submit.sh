pycbc_submit_dax --no-grid --no-create-proxy \
--local-dir ./ \
--no-query-db \
--executation-sites condorpool_symlink \
--staging-sites condorpool_symlink=local \
--dax gw.dax
