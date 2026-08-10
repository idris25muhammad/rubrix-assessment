from config import PORT
from modules import create_app
from werkzeug.middleware.proxy_fix import ProxyFix

app = create_app()

# Enable proxy headers support (X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Prefix, X-Forwarded-Host)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if __name__ == "__main__":
    app.run(debug=True, port=PORT)

