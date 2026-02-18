import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import Config

class Notifier:
    @staticmethod
    def send_alert(product_name, pharmacy, price, url):
        if not Config.EMAIL_USER or not Config.EMAIL_PASS:
            print("Email credentials not configured. Skipping alert.")
            return

        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_USER
        msg['To'] = Config.EMAIL_TO
        msg['Subject'] = f"🚨 ALERTA DE PREÇO: {product_name}"

        body = f"""
        Olá!
        
        O preço do medicamento {product_name} baixou na {pharmacy}!
        
        Preço da Caixa (com frete/kit): R$ {price:.2f}
        Link: {url}
        
        ---
        Monitor de Preços Automático
        """
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
            server.starttls()
            server.login(Config.EMAIL_USER, Config.EMAIL_PASS)
            text = msg.as_string()
            server.sendmail(Config.EMAIL_USER, Config.EMAIL_TO, text)
            server.quit()
            print(f"Alerta enviado para {Config.EMAIL_TO}")
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
