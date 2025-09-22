# Используем легковесный Linux
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
# Установка зависимостей и сборка downward
RUN apt update && \
    apt install -y \
        build-essential \
        cmake \
        git \
        python3 \
        python3-pip \
        wget \
        vim \
    && rm -rf /var/lib/apt/lists/*

RUN python3 --version  # Должно быть 3.10+

# Скачиваем и собираем downward
WORKDIR /app
RUN git clone https://github.com/aibasel/downward.git . 
RUN ./build.py
RUN ln -s /app/fast-downward.py /usr/local/bin/fast-downward.py
ENV PYTHONPATH="/app:${PYTHONPATH}"
CMD ["fast-downward.py", "--help"]
ENTRYPOINT ["/app/fast-downward.py"]
# usage
#  cd /curdir/
# docker build -t downward-planner .
# далее - см. вызов в action_sequencing