FROM ultralytics/ultralytics:latest

WORKDIR /workspace

# Install redis client for status reporting back to host
RUN pip install redis --quiet

COPY train.py .

ENTRYPOINT ["python", "train.py"]
