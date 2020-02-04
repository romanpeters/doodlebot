FROM python:3.7

ADD . /bot
WORKDIR /bot
RUN pip install --no-cache-dir -U -r requirements.txt

CMD ["python", "-u", "main.py"]