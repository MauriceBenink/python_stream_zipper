# https://github.com/MauriceBenink/python_pytest_base
FROM lib-test:latest
# docker build -t stream-zipper-test
# docker run -it -v {project_root}:/package stream-zipper-test

RUN pip3 install pympler