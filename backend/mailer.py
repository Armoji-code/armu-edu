import smtplib
import ssl
from email.message import EmailMessage


def _get_smtp_cfg():
    from models.school import School
    school = School.query.first()
    if not school:
        return {}
    return (school.settings or {}).get("smtp", {})


def smtp_configured():
    cfg = _get_smtp_cfg()
    return bool(cfg.get("host") and cfg.get("username"))


def send_reset_email(to_email: str, code: str, user_name: str):
    cfg = _get_smtp_cfg()
    host = cfg.get("host", "").strip()
    if not host:
        raise ValueError("SMTP not configured — set host in Admin → Settings → Email")

    port     = int(cfg.get("port", 587))
    username = cfg.get("username", "").strip()
    password = cfg.get("password", "").strip()
    from_addr = cfg.get("from_email", "").strip() or username
    use_tls  = bool(cfg.get("use_tls", True))

    msg = EmailMessage()
    msg["Subject"] = "Armu — Password Reset Code"
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.set_content(
        f"Hi {user_name},\n\n"
        f"Your password reset code is:\n\n"
        f"  {code}\n\n"
        f"This code expires in 15 minutes.\n"
        f"If you did not request a reset, ignore this email.\n\n"
        f"— Armu"
    )

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as srv:
            if username:
                srv.login(username, password)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as srv:
            if use_tls:
                srv.starttls(context=context)
            if username:
                srv.login(username, password)
            srv.send_message(msg)


def send_test_email(to_email: str):
    cfg = _get_smtp_cfg()
    host = cfg.get("host", "").strip()
    if not host:
        raise ValueError("SMTP not configured — set host in Admin → Settings → Email")

    port     = int(cfg.get("port", 587))
    username = cfg.get("username", "").strip()
    password = cfg.get("password", "").strip()
    from_addr = cfg.get("from_email", "").strip() or username
    use_tls  = bool(cfg.get("use_tls", True))

    msg = EmailMessage()
    msg["Subject"] = "Armu — SMTP test"
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.set_content("This is a test email from Armu. Your SMTP settings are working.")

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as srv:
            if username:
                srv.login(username, password)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as srv:
            if use_tls:
                srv.starttls(context=context)
            if username:
                srv.login(username, password)
            srv.send_message(msg)
