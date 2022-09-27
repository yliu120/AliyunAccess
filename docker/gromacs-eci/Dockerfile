# Build the image by the following command:
#   docker build -t <image_name>:<tag> .
FROM nvidia/cuda:11.4.1-devel-ubuntu20.04 AS builder
ENV DEBIAN_FRONTEND noninteractive
WORKDIR /root
RUN apt-get update && \
    apt-get install -y --no-install-recommends cmake wget python3

# Install CUDA-Aware Openmpi
RUN wget https://download.open-mpi.org/release/open-mpi/v4.1/openmpi-4.1.4.tar.bz2 && \
    tar xvf openmpi-4.1.4.tar.bz2 && \
    cd openmpi-4.1.4 && \
    ./configure --with-cuda --prefix=/usr/local/openmpi/ && \
    make -j4 install

# Install Gromacs 2022.3
RUN wget https://ftp.gromacs.org/gromacs/gromacs-2022.3.tar.gz && \
    tar xvf gromacs-2022.3.tar.gz && \
    cd gromacs-2022.3 && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
          -DGMX_MPI=on -DMPI_CXX_COMPILER=/usr/local/openmpi/bin/mpic++ \
          -DGMX_GPU=CUDA \
          -DGMX_BUILD_OWN_FFTW=ON -DGMX_SIMD=AVX_512 \
          -DCMAKE_BUILD_TYPE=Release && \
    make -j4 install

FROM nvidia/cuda:11.4.1-runtime-ubuntu20.04
COPY --from=builder /usr/local/openmpi /usr/local/openmpi
COPY --from=builder /usr/local/gromacs /usr/local/gromacs

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 vim ssh sudo

ENV PATH=$PATH:/usr/local/gromacs/bin:/usr/local/openmpi/bin
ENV OMPI_ALLOW_RUN_AS_ROOT=1
ENV OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

RUN useradd -ms /bin/bash gromacs && \
    usermod -aG sudo gromacs
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

WORKDIR /root/