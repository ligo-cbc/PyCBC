#!/bin/bash -v

set -e

OS_VERSION=${1}
TRAVIS_TAG=${2}
PYCBC_CODE=${3}
LALSUITE_CODE=${4}

echo -e "\\n>> [`date`] Inside CentOS ${OS_VERSION}"
echo -e "\\n>> [`date`] Release tag is ${TRAVIS_TAG}"
echo -e "\\n>> [`date`] Using PyCBC code ${PYCBC_CODE}"
echo -e "\\n>> [`date`] Using lalsuite code ${LALSUITE_CODE}"

cat /etc/redhat-release

if [ "x${OS_VERSION}" == "x6" ] ; then
  echo -e "\\n>> [`date`] Building pycbc_inspiral bundle for CentOS 6"

  # install requirements into docker container
  yum install -y gcc gcc-c++ gcc-gfortran python-devel pcre-devel autoconf automake make zlib-devel libpng-devel libjpeg-devel libsqlite3-dev sqlite-devel
  ln -s /usr/bin/g++ /usr/bin/g++-4.4.7
  ln -s /usr/bin/gfortran /usr/bin/gfortran-4.4.7
  yum -y install ant asciidoc fop docbook-style-xsl.noarch R-devel

  # create working dir for build script
  BUILD=/pycbc/build
  mkdir -p ${BUILD}
  export PYTHONUSERBASE=${BUILD}/.local
  export XDG_CACHE_HOME=${BUILD}/.cache

  # run the einstein at home build and test script
  pushd ${BUILD}
  /pycbc/tools/einsteinathome/pycbc_build_eah.sh ${LALSUITE_CODE} ${PYCBC_CODE} --silent-build
  popd
fi

if [ "x${OS_VERSION}" == "x7" ] ; then
  echo -e "\\n>> [`date`] Building pycbc virtual environment for CentOS 7"

  rpm -ivh http://software.ligo.org/lscsoft/scientific/7.2/x86_64/production/lscsoft-production-config-1.3-1.el7.noarch.rpm
  yum clean all
  yum makecache 
  yum update
  yum -y install lscsoft-backports-config
  yum -y install lscsoft-epel-config
  curl http://download.pegasus.isi.edu/wms/download/rhel/7/pegasus.repo > /etc/yum.repos.d/pegasus.repo
  yum clean all
  yum makecache
  yum update
  yum -y install lscsoft-ius-config
  yum clean all
  yum makecache
  yum -y install git2u-all
  yum -y install lscsoft-all

  rpm --nodeps -e lal-python-6.18.0-1.el7.x86_64 lalstochastic-octave-1.1.20-1.el7.x86_64 laldetchar-octave-0.3.5-1.el7.x86_64 lalinference-devel-1.9.0-1.el7.x86_64 lalxml-devel-1.2.4-1.el7.x86_64 gstlal-calibration-1.1.4-2.el7.x86_64 lal-octave-6.18.0-1.el7.x86_64 lalburst-octave-1.4.4-1.el7.x86_64 lalinspiral-octave-1.7.7-1.el7.x86_64 lalstochastic-1.1.20-1.el7.x86_64 gstlal-ugly-1.2.0-2.el7.x86_64 lalsimulation-1.7.0-1.el7.x86_64 lalsimulation-devel-1.7.0-1.el7.x86_64 lalpulsar-octave-1.16.0-1.el7.x86_64 laldetchar-devel-0.3.5-1.el7.x86_64 lalinspiral-debuginfo-1.7.7-1.el7.x86_64 lalmetaio-devel-1.3.1-1.el7.x86_64 lalinference-python-1.9.0-1.el7.x86_64 lalapps-6.21.0-1.el7.x86_64 lalmetaio-debuginfo-1.3.1-1.el7.x86_64 lalframe-devel-1.4.3-1.el7.x86_64 python-pylal-0.13.1-1.el7.x86_64 gstlal-ugly-devel-1.2.0-2.el7.x86_64 lalapps-debuginfo-6.21.0-1.el7.x86_64 lalburst-1.4.4-1.el7.x86_64 lalxml-python-1.2.4-1.el7.x86_64 lalinference-octave-1.9.0-1.el7.x86_64 lalframe-debuginfo-1.4.3-1.el7.x86_64 lalinspiral-1.7.7-1.el7.x86_64 lalburst-devel-1.4.4-1.el7.x86_64 lalsimulation-python-1.7.0-1.el7.x86_64 gstlal-inspiral-1.3.0-2.el7.x86_64 lscsoft-pylal-1.1-1.el7.noarch lscsoft-lalsuite-2.9-1.el7.noarch lalinference-1.9.0-1.el7.x86_64 lalstochastic-devel-1.1.20-1.el7.x86_64 lal-debuginfo-6.18.0-1.el7.x86_64 lal-6.18.0-1.el7.x86_64 lalstochastic-python-1.1.20-1.el7.x86_64 laldetchar-python-0.3.5-1.el7.x86_64 lalxml-debuginfo-1.2.4-1.el7.x86_64 lalxml-1.2.4-1.el7.x86_64 lalinspiral-devel-1.7.7-1.el7.x86_64 lalpulsar-python-1.16.0-1.el7.x86_64 laldetchar-debuginfo-0.3.5-1.el7.x86_64 lscsoft-gstlal-1.9-1.el7.noarch lalpulsar-1.16.0-1.el7.x86_64 lalxml-octave-1.2.4-1.el7.x86_64 lalframe-python-1.4.3-1.el7.x86_64 gstlal-inspiral-devel-1.3.0-2.el7.x86_64 lalsimulation-debuginfo-1.7.0-1.el7.x86_64 lalmetaio-1.3.1-1.el7.x86_64 laldetchar-0.3.5-1.el7.x86_64 lalburst-python-1.4.4-1.el7.x86_64 lalframe-octave-1.4.3-1.el7.x86_64 lscsoft-gstlal-dev-1.0-1.el7.noarch lalframe-1.4.3-1.el7.x86_64 lalsimulation-octave-1.7.0-1.el7.x86_64 lalmetaio-octave-1.3.1-1.el7.x86_64 lalpulsar-devel-1.16.0-1.el7.x86_64 lalburst-debuginfo-1.4.4-1.el7.x86_64 gstlal-devel-1.1.0-2.el7.x86_64 lalinference-debuginfo-1.9.0-1.el7.x86_64 lal-devel-6.18.0-1.el7.x86_64 lalsuite-extra-1.1.0-1.el7.noarch lalinspiral-python-1.7.7-1.el7.x86_64 lalpulsar-debuginfo-1.16.0-1.el7.x86_64 gstlal-1.1.0-2.el7.x86_64 lalstochastic-debuginfo-1.1.20-1.el7.x86_64 lalmetaio-python-1.3.1-1.el7.x86_64 lscsoft-lalsuite-dev-1.7-1.el7.noarch skyarea-0.2.1-1.el7.noarch

  TRAVIS_TAG="vX.Y.Z"
  CVMFS_PATH=/cvmfs/oasis.opensciencegrid.org/ligo/sw/pycbc/x86_64_rhel_7/virtualenv
  mkdir -p ${CVMFS_PATH}
  VENV_PATH=${CVMFS_PATH}/pycbc-${TRAVIS_TAG}
  pip install virtualenv
  virtualenv ${VENV_PATH}
  echo 'export PYTHONUSERBASE=${VIRTUAL_ENV}/.local' >> ${VENV_PATH}/bin/activate
  echo 'export XDG_CACHE_HOME=${VIRTUAL_ENV}/.cache' >> ${VENV_PATH}/bin/activate
  source ${VENV_PATH}/bin/activate
  pip install --upgrade pip
  pip install six packaging appdirs
  pip install --upgrade setuptools

  pip install "numpy>=1.6.4" unittest2 python-cjson Cython decorator
  SWIG_FEATURES="-cpperraswarn -includeall -I/usr/include/openssl" pip install M2Crypto

  mkdir -p ${VIRTUAL_ENV}/src
  cd ${VIRTUAL_ENV}/src
  git clone https://github.com/lscsoft/lalsuite.git
  cd ${VIRTUAL_ENV}/src/lalsuite
  git checkout ${LALSUITE_CODE}
  ./00boot
  ./configure --prefix=${VIRTUAL_ENV}/opt/lalsuite --enable-swig-python --disable-lalstochastic --disable-lalxml --disable-lalinference --disable-laldetchar --disable-lalapps
  make -j 32 install
  echo 'source ${VIRTUAL_ENV}/opt/lalsuite/etc/lalsuite-user-env.sh' >> ${VIRTUAL_ENV}/bin/activate
  deactivate

  source ${VENV_PATH}/bin/activate
  cd $VIRTUAL_ENV/src/lalsuite/lalapps
  LIBS="-lhdf5_hl -lhdf5 -ldl -lz" ./configure --prefix=${VIRTUAL_ENV}/opt/lalsuite --enable-static-binaries --disable-lalinference --disable-lalburst --disable-lalpulsar --disable-lalstochastic
  cd $VIRTUAL_ENV/src/lalsuite/lalapps/src/lalapps
  make
  cd $VIRTUAL_ENV/src/lalsuite/lalapps/src/inspiral
  make lalapps_inspinj
  cp lalapps_inspinj $VIRTUAL_ENV/bin
  cd $VIRTUAL_ENV/src/lalsuite/lalapps/src/ring
  make lalapps_coh_PTF_inspiral
  cp lalapps_coh_PTF_inspiral $VIRTUAL_ENV/bin

  pip install http://download.pegasus.isi.edu/pegasus/4.7.4/pegasus-python-source-4.7.4.tar.gz
  pip install git+https://github.com/ligovirgo/dqsegdb@clean_pip_install_1_4_1#egg=dqsegdb

  cd /pycbc
  python setup.py install

  pip install pycbc-pylal

  pip install 'matplotlib==1.5.3'
  pip install ipython
  pip install jupyter

cat << EOF >> $VIRTUAL_ENV/bin/activate

# If a suitable MKL exists, set it up
if [ -f /opt/intel/composer_xe_2015/mkl/bin/mklvars.sh ] ; then
  . /opt/intel/composer_xe_2015/mkl/bin/mklvars.sh intel64
elif [ -f /ldcg/intel/2017u0/compilers_and_libraries_2017.0.098/linux/mkl/bin/mklvars.sh ] ; then
  . /ldcg/intel/2017u0/compilers_and_libraries_2017.0.098/linux/mkl/bin/mklvars.sh intel64
fi

# Use the revison 11 ROM data from CVMFS
export LAL_DATA_PATH=/cvmfs/oasis.opensciencegrid.org/ligo/sw/pycbc/lalsuite-extra/11/share/lalsimulation
EOF

  deactivate
fi 

echo -e "\\n>> [`date`] CentOS Docker script exiting"

exit 0
