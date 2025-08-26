from flask import Flask, render_template, request, send_file, redirect, url_for, session
import io, re, functools

app = Flask(__name__)
app.secret_key = "super_secret_change_this"

# ---------------- Password Config ----------------
ADMIN_PASS = "mypass123"   # change this

# ---------------- Helpers ----------------
def allowed(filename, exts):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts

def make_c_ident(name: str, fallback="data") -> str:
    name = (name or "").strip()
    name = re.sub(r"[^0-9a-zA-Z_]", "_", name)
    if not name:
        name = fallback
    if re.match(r"^\d", name):
        name = f"_{name}"
    return name

def bytes_to_c_array(data: bytes, varname="data", wrap=32):
    varname = make_c_ident(varname or "data")
    if varname.upper().startswith("SRCHUB"):
        varname = varname.replace("SRCHUB", "SARKAR")
    wrap = 32
    lines = [f"unsigned char {varname}[] = {{"]

    line = "  "
    for i, b in enumerate(data):
        line += f"0x{b:02x}"
        if i != len(data) - 1:
            line += ", "
        if (i + 1) % wrap == 0 and i != len(data) - 1:
            lines.append(line)
            line = "  "
    if line.strip():
        lines.append(line)

    lines.append("};")
    return "\n".join(lines).encode("utf-8")

def c_array_to_bytes(content: str) -> bytes:
    content = re.sub(r"//.*?$|/\*.*?\*/", "", content, flags=re.M | re.S)
    m = re.search(r"\{([^}]*)\}", content, re.S)
    if not m:
        raise ValueError("No byte array found in .h")

    body = m.group(1)
    tokens = re.findall(r"0x[0-9a-fA-F]{1,2}|\d{1,3}", body)
    data = bytearray()
    for t in tokens:
        v = int(t, 16) if t.lower().startswith("0x") else int(t)
        if not 0 <= v <= 255:
            raise ValueError(f"Byte value out of range: {t}")
        data.append(v)
    return bytes(data)

# ---------------- Web Control ----------------
web_enabled = True

def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

# ---------------- Admin Routes ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        return "❌ Wrong Password"
    return render_template("admin_login.html")

@app.route("/admin/panel")
@login_required
def admin_panel():
    global web_enabled
    status = "🟢 Online" if web_enabled else "🔴 Offline"
    return render_template("admin_panel.html", status=status)

@app.route("/admin/toggle")
@login_required
def admin_toggle():
    global web_enabled
    web_enabled = not web_enabled
    return redirect(url_for("admin_panel"))

@app.route("/admin/logout")
@login_required
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))

# ---------------- File Conversion ----------------
@app.route("/convert/<action>", methods=["POST"])
def convert(action):
    global web_enabled
    if not web_enabled:
        return "🚫 Website is Offline by Admin", 403

    if "file" not in request.files:
        return "❌ No file uploaded", 400

    f = request.files["file"]

    try:
        if action == "png-to-h":
            if not allowed(f.filename, {"png", "jpg", "jpeg", "bmp"}):
                return "❌ Invalid image file", 400
            data = f.read()
            varname = request.form.get("varname") or "SRCHUB_data"
            out = bytes_to_c_array(data, varname=varname)
            return send_file(io.BytesIO(out), as_attachment=True, download_name="converted.h")

        elif action == "h-to-png":
            if not allowed(f.filename, {"h"}):
                return "❌ Invalid header file", 400
            content = f.read().decode("utf-8", errors="ignore")
            data = c_array_to_bytes(content)
            return send_file(io.BytesIO(data), as_attachment=True, download_name="converted.png", mimetype="image/png")

        elif action == "ttf-to-h":
            if not allowed(f.filename, {"ttf"}):
                return "❌ Invalid font file", 400
            data = f.read()
            varname = request.form.get("varname") or "font_data"
            out = bytes_to_c_array(data, varname=varname)
            return send_file(io.BytesIO(out), as_attachment=True, download_name="converted.h")

        elif action == "h-to-ttf":
            if not allowed(f.filename, {"h"}):
                return "❌ Invalid header file", 400
            content = f.read().decode("utf-8", errors="ignore")
            data = c_array_to_bytes(content)
            return send_file(io.BytesIO(data), as_attachment=True, download_name="converted.ttf", mimetype="font/ttf")

        else:
            return "❌ Unknown action", 400

    except Exception as e:
        return f"⚠️ Error: {str(e)}", 400

# ---------------- Aliases ----------------
@app.route("/png-to-h", methods=["POST"])
def alias_png_to_h(): return convert("png-to-h")

@app.route("/h-to-png", methods=["POST"])
def alias_h_to_png(): return convert("h-to-png")

@app.route("/ttf-to-h", methods=["POST"])
def alias_ttf_to_h(): return convert("ttf-to-h")

@app.route("/h-to-ttf", methods=["POST"])
def alias_h_to_ttf(): return convert("h-to-ttf")

@app.route("/png2h", methods=["POST"])
def alias_png2h(): return convert("png-to-h")

@app.route("/h2png", methods=["POST"])
def alias_h2png(): return convert("h-to-png")

@app.route("/ttf2h", methods=["POST"])
def alias_ttf2h(): return convert("ttf-to-h")

@app.route("/h2ttf", methods=["POST"])
def alias_h2ttf(): return convert("h-to-ttf")

# ---------------- Index ----------------
@app.route("/")
def index():
    global web_enabled
    if not web_enabled:
        return "🚫 Website is Offline by Admin", 403
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5080, debug=True)