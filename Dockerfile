FROM python:3.9-alpine

WORKDIR /app
RUN pip3 install --upgrade pip
RUN pip3 install flask
RUN pip3 install requests
RUN pip3 install ibm_watson
RUN pip3 install gunicorn
RUN pip3 install websocket-client

# Copy runtime files from the current directory into the container at /app
ADD speech-demo.py /app
ADD websocket-test.py /app
RUN mkdir /app/static
ADD static /app/static/
RUN mkdir /app/templates
ADD templates /app/templates/
RUN date > /app/static/build.txt

# Run app.py when the container launches
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 speech-demo:app
