from email.header import decode_header
import email

import uuid
import time
import json

import imaplib
import requests
import markdown

from datetime import datetime
from dataclasses import dataclass, asdict

import mysql.connector

from concurrent.futures import ThreadPoolExecutor

# Matrix access token; required
# See readme for more info
access_token:str = ""

# MySQL details
db_user:str = ""
db_passwd:str = ""
db_host:str = "localhost"
db_database:str = "email_matrix_data"

@dataclass
class EmailData:
    subject:str = None
    from_:str = None
    date_:str = None
    body:str = None
    filename:str = None
    payload:str = None
    orig_message_id:str = None
    orig_references:str = None

class EMailBot(object):
    main_url:str = "https://matrix.zuzu.im" # MATRIX MAIN_URL

    def __init__(self, email:str, password:str, host:str, roomId:str, folder:str="INBOX", thread_num:int=1):
        self.roomId = roomId
        self.thread_num = thread_num
        self.imap = imaplib.IMAP4_SSL(host, 993)
        self.imap.login(email, password)
        self.imap.select(folder)
        # print(f"[{datetime.now().strftime('%H:%M:%S, %d-%b-%Y')}]: Started threadNum '{self.thread_num}'")

    def close_imap(self):
        self.imap.close()
        self.imap.logout()

    def create_thread(self, data:EmailData):
        subject:str = f"*From:* {data.from_}<br>*Subject:* {data.subject}<br>*Date:* {data.date_}"
        headers:dict = {"Authorization":f"Bearer {access_token}"}
        data_post:dict = {"body":subject,
            "format":"org.matrix.custom.html",
            "formatted_body":markdown.markdown(subject).replace("<em>", "<strong>").replace("</em>", "</strong>"),
            "msgtype":"m.text"}
        res = requests.post(f"{self.main_url}/_matrix/client/v3/rooms/{self.roomId}/send/m.room.message", headers=headers, json=data_post)
        event_id = res.json()["event_id"]
        txnId = uuid.uuid4()
        headers:dict = {"Authorization":f"Bearer {access_token}"}
        data_post = {
            "msgtype":"m.text",
            "body":data.body,
            "format":"org.matrix.custom.html",
            "formatted_body":markdown.markdown(data.body).replace("<em>", "<strong>").replace("</em>", "</strong>"),
            "m.relates_to":{
                "rel_type":"m.thread",
                "event_id":event_id,
                "m.in_reply_to":{
                    "event_id":event_id
                }
            }
        }
        res = requests.put(f"{self.main_url}/_matrix/client/v3/rooms/{self.roomId}/send/m.room.message/{txnId}", headers=headers, json=data_post)
        return res.json()["event_id"], txnId

    def parse_email(self, raw_email):
        msg = email.message_from_bytes(raw_email)
        data = EmailData()

        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")

        from_ = msg.get("From")
        date_ = msg.get("Date")
        orig_message_id = msg.get("Message-ID")
        orig_references = msg.get("References", "")

        data.subject = subject
        data.from_ = from_
        data.date_ = date_
        data.orig_message_id = orig_message_id
        data.orig_references = orig_references

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = part.get_payload(decode=True).decode(errors="replace")
                    data.body = body

                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    payload = part.get_payload(decode=True)
                    data.filename = filename
                    data.payload = payload
        else:
            body = msg.get_payload(decode=True).decode(errors="replace")
            data.body = body
        return data

    def insert_data(self, subject, from_, date_, body, filename, payload, orig_message_id, orig_references, event_id, tnxId):
        con = mysql.connector.connect(
            user=db_user,
            password=db_passwd,
            host=db_host,
            database=db_database
        )
        cur = con.cursor(dictionary=True)
        cur.execute("INSERT INTO data VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [subject, from_, date_, body, filename, payload, orig_message_id, orig_references, event_id, str(tnxId)])
        con.commit()
        cur.close()
        con.close()
    
    def pool_messages(self):
        status, data = self.imap.uid("search", None, "UNSEEN", "SINCE", datetime.now().strftime("%d-%b-%Y"))
        uids = data[0].split()[::-1]

        for uid in uids:
            status, msg_data = self.imap.uid("fetch", uid, "(RFC822)")
            print(f"[{datetime.now().strftime('%H:%M:%S, %d-%b-%Y')}]: {status} threadNum '{self.thread_num}'")
            data = self.parse_email(msg_data[0][1])
            data_dict = asdict(data)
            event_id, tnxId = self.create_thread(data)
            self.imap.uid("store", uid, "+FLAGS", "\\Seen")
            self.insert_data(**data_dict, event_id=event_id, tnxId=tnxId)

def func_main(data_config, thread_num):
    while True:
        bot = EMailBot(
            data_config["email"],
            data_config["password"],
            data_config["host"],
            data_config["roomId"],
            data_config["folder"],
            thread_num=thread_num
        )
        try:
            bot.pool_messages()
            bot.close_imap()
            time.sleep(15)
        except KeyboardInterrupt:
            return
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S, %d-%b-%Y')}]: Error ({e}) threadNum '{thread_num}'")

if __name__ == "__main__":
    data = json.loads(open("config.json", "r").read())["data"]

    with ThreadPoolExecutor(max_workers=10) as exec:
        futures = [exec.submit(func_main, data[_], _+1) for _ in range(len(data))]
