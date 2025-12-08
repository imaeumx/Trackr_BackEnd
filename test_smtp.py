import smtplib

# Replace with your Gmail and App Password
gmail_user = 'your_email@gmail.com'
app_password = 'your_app_password'

sent_from = gmail_user
to = ['recipient_email@gmail.com']  # You can use your own email for testing
subject = 'SMTP Test'
body = 'This is a test email from Python shell using Gmail SMTP.'

email_text = f"""\
From: {sent_from}
To: {', '.join(to)}
Subject: {subject}

{body}
"""

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(gmail_user, app_password)
    server.sendmail(sent_from, to, email_text)
    server.close()
    print('Email sent successfully!')
except Exception as e:
    print('Error sending email:', e)