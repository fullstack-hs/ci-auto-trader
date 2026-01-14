FROM ubuntu:22.04
WORKDIR /app
RUN apt-get update && \
    apt-get install -y python3 python3-pip liblapack-dev libblas-dev gfortran wget build-essential
RUN echo "/usr/local/lib" >> /etc/ld.so.conf.d/local.conf && ldconfig
RUN pip3 install --upgrade pip setuptools wheel
COPY . /app
RUN pip3 install  --ignore-installed -r requirements.txt
ENV PYTHONUNBUFFERED=1
CMD ["python3", "run.py"]