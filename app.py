
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3, os

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

LOGIN_USER = "admin"
LOGIN_PASSWORD = "Ayoub@2025"

def db():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS avances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            titre TEXT NOT NULL,
            description TEXT,
            date_creation TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS versements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            avance_id INTEGER NOT NULL,
            montant REAL NOT NULL,
            commentaire TEXT,
            date_enregistrement TEXT NOT NULL,
            FOREIGN KEY (avance_id) REFERENCES avances(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS depenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            avance_id INTEGER NOT NULL,
            montant REAL NOT NULL,
            description TEXT NOT NULL,
            justificatif TEXT,
            date_enregistrement TEXT NOT NULL,
            FOREIGN KEY (avance_id) REFERENCES avances(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entrees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            montant REAL NOT NULL,
            description TEXT NOT NULL,
            date_enregistrement TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","")
        password = request.form.get("password","")
        if username == LOGIN_USER and password == LOGIN_PASSWORD:
            session["user"] = username
            flash("Connexion réussie.", "success")
            return redirect(url_for("dashboard"))
        flash("Identifiants invalides.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("login"))

@app.before_request
def require_login():
    if request.endpoint in ("login", "static"):
        return
    if "user" not in session:
        return redirect(url_for("login"))

@app.route("/")
def dashboard():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM avances ORDER BY date_creation DESC")
    avances = cur.fetchall()
    cur.execute("SELECT COALESCE(SUM(montant),0) AS t FROM versements")
    total_versements = cur.fetchone()["t"]
    cur.execute("SELECT COALESCE(SUM(montant),0) AS t FROM depenses")
    total_depenses = cur.fetchone()["t"]
    cur.execute("SELECT COALESCE(SUM(montant),0) AS t FROM entrees")
    total_entrees = cur.fetchone()["t"]
    conn.close()
    return render_template("dashboard.html",
                           avances=avances,
                           total_versements=total_versements,
                           total_depenses=total_depenses,
                           total_entrees=total_entrees)

from werkzeug.utils import secure_filename

@app.route("/avance/new", methods=["GET","POST"])
def add_avance():
    if request.method == "POST":
        titre = request.form.get("titre","").strip()
        description = request.form.get("description","").strip()
        if not titre:
            flash("Le titre est obligatoire.", "danger")
            return render_template("add_avance.html")
        code = "AV-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        date_creation = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO avances (code, titre, description, date_creation) VALUES (?,?,?,?)",
                    (code, titre, description, date_creation))
        conn.commit()
        conn.close()
        flash("Avance créée.", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_avance.html")

@app.route("/avance/<int:avance_id>")
def avance_detail(avance_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM avances WHERE id=?", (avance_id,))
    avance = cur.fetchone()
    if not avance:
        conn.close()
        flash("Avance introuvable.", "warning")
        return redirect(url_for("dashboard"))
    cur.execute("SELECT * FROM versements WHERE avance_id=? ORDER BY date_enregistrement DESC, id DESC", (avance_id,))
    versements = cur.fetchall()
    cur.execute("SELECT * FROM depenses WHERE avance_id=? ORDER BY date_enregistrement DESC, id DESC", (avance_id,))
    depenses = cur.fetchall()
    total_v = sum([v["montant"] for v in versements]) if versements else 0
    total_d = sum([d["montant"] for d in depenses]) if depenses else 0
    solde = total_v - total_d
    conn.close()
    return render_template("avance_detail.html", avance=avance, versements=versements, depenses=depenses,
                           total_v=total_v, total_d=total_d, solde=solde)

@app.route("/avance/edit/<int:avance_id>", methods=["GET","POST"])
def edit_avance(avance_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM avances WHERE id=?", (avance_id,))
    avance = cur.fetchone()
    if not avance:
        conn.close()
        flash("Avance introuvable.", "warning")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        titre = request.form.get("titre","").strip()
        description = request.form.get("description","").strip()
        if not titre:
            flash("Le titre est obligatoire.", "danger")
            return render_template("edit_avance.html", avance=avance)
        cur.execute("UPDATE avances SET titre=?, description=? WHERE id=?", (titre, description, avance_id))
        conn.commit()
        conn.close()
        flash("Avance modifiée.", "success")
        return redirect(url_for("avance_detail", avance_id=avance_id))
    conn.close()
    return render_template("edit_avance.html", avance=avance)

@app.route("/avance/delete/<int:avance_id>", methods=["POST"])
def delete_avance(avance_id):
    conn = db()
    cur = conn.cursor()
    # Delete files of depenses
    cur.execute("SELECT justificatif FROM depenses WHERE avance_id=?", (avance_id,))
    for row in cur.fetchall():
        if row["justificatif"]:
            try:
                os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["justificatif"]))
            except Exception:
                pass
    cur.execute("DELETE FROM versements WHERE avance_id=?", (avance_id,))
    cur.execute("DELETE FROM depenses WHERE avance_id=?", (avance_id,))
    cur.execute("DELETE FROM avances WHERE id=?", (avance_id,))
    conn.commit()
    conn.close()
    flash("Avance supprimée.", "success")
    return redirect(url_for("dashboard"))

@app.route("/versement/new/<int:avance_id>", methods=["GET","POST"])
def add_versement(avance_id):
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        commentaire = request.form.get("commentaire","").strip()
        if montant <= 0:
            flash("Montant invalide.", "danger")
            return render_template("add_versement.html", avance_id=avance_id)
        date_enregistrement = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO versements (avance_id, montant, commentaire, date_enregistrement) VALUES (?,?,?,?)",
                    (avance_id, montant, commentaire, date_enregistrement))
        conn.commit()
        conn.close()
        flash("Versement ajouté.", "success")
        return redirect(url_for("avance_detail", avance_id=avance_id))
    return render_template("add_versement.html", avance_id=avance_id)

@app.route("/versement/edit/<int:versement_id>", methods=["GET","POST"])
def edit_versement(versement_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM versements WHERE id=?", (versement_id,))
    v = cur.fetchone()
    if not v:
        conn.close()
        flash("Versement introuvable.", "warning")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        commentaire = request.form.get("commentaire","").strip()
        if montant <= 0:
            flash("Montant invalide.", "danger")
            return render_template("edit_versement.html", v=v)
        cur.execute("UPDATE versements SET montant=?, commentaire=? WHERE id=?", (montant, commentaire, versement_id))
        avance_id = v["avance_id"]
        conn.commit()
        conn.close()
        flash("Versement modifié.", "success")
        return redirect(url_for("avance_detail", avance_id=avance_id))
    conn.close()
    return render_template("edit_versement.html", v=v)

@app.route("/versement/delete/<int:versement_id>", methods=["POST"])
def delete_versement(versement_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT avance_id FROM versements WHERE id=?", (versement_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Versement introuvable.", "warning")
        return redirect(url_for("dashboard"))
    avance_id = row["avance_id"]
    cur.execute("DELETE FROM versements WHERE id=?", (versement_id,))
    conn.commit()
    conn.close()
    flash("Versement supprimé.", "success")
    return redirect(url_for("avance_detail", avance_id=avance_id))

@app.route("/depense/new/<int:avance_id>", methods=["GET","POST"])
def add_depense(avance_id):
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        description = request.form.get("description","").strip()
        if montant <= 0 or not description:
            flash("Montant/description invalides.", "danger")
            return render_template("add_depense.html", avance_id=avance_id)
        filename = None
        file = request.files.get("justificatif")
        if file and file.filename:
            if allowed_file(file.filename):
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                safe = secure_filename(file.filename)
                filename = datetime.now().strftime("%Y%m%d%H%M%S_") + safe
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            else:
                flash("Format de justificatif non autorisé (PDF, JPG, PNG).", "danger")
                return render_template("add_depense.html", avance_id=avance_id)
        date_enregistrement = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO depenses (avance_id, montant, description, justificatif, date_enregistrement)
            VALUES (?,?,?,?,?)
        """, (avance_id, montant, description, filename, date_enregistrement))
        conn.commit()
        conn.close()
        flash("Dépense ajoutée.", "success")
        return redirect(url_for("avance_detail", avance_id=avance_id))
    return render_template("add_depense.html", avance_id=avance_id)

@app.route("/depense/edit/<int:depense_id>", methods=["GET","POST"])
def edit_depense(depense_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM depenses WHERE id=?", (depense_id,))
    d = cur.fetchone()
    if not d:
        conn.close()
        flash("Dépense introuvable.", "warning")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        description = request.form.get("description","").strip()
        replace_file = request.files.get("justificatif")
        filename = d["justificatif"]
        if montant <= 0 or not description:
            flash("Montant/description invalides.", "danger")
            return render_template("edit_depense.html", d=d)
        if replace_file and replace_file.filename:
            if allowed_file(replace_file.filename):
                if filename:
                    try:
                        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                    except Exception:
                        pass
                safe = secure_filename(replace_file.filename)
                filename = datetime.now().strftime("%Y%m%d%H%M%S_") + safe
                replace_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            else:
                flash("Format de justificatif non autorisé (PDF, JPG, PNG).", "danger")
                return render_template("edit_depense.html", d=d)
        cur.execute("UPDATE depenses SET montant=?, description=?, justificatif=? WHERE id=?",
                    (montant, description, filename, depense_id))
        avance_id = d["avance_id"]
        conn.commit()
        conn.close()
        flash("Dépense modifiée.", "success")
        return redirect(url_for("avance_detail", avance_id=avance_id))
    conn.close()
    return render_template("edit_depense.html", d=d)

@app.route("/depense/delete/<int:depense_id>", methods=["POST"])
def delete_depense(depense_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT avance_id, justificatif FROM depenses WHERE id=?", (depense_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Dépense introuvable.", "warning")
        return redirect(url_for("dashboard"))
    avance_id = row["avance_id"]
    justificatif = row["justificatif"]
    if justificatif:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], justificatif))
        except Exception:
            pass
    cur.execute("DELETE FROM depenses WHERE id=?", (depense_id,))
    conn.commit()
    conn.close()
    flash("Dépense supprimée.", "success")
    return redirect(url_for("avance_detail", avance_id=avance_id))

@app.route("/entrees")
def entrees():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM entrees ORDER BY date_enregistrement DESC, id DESC")
    rows = cur.fetchall()
    conn.close()
    return render_template("entrees.html", entrees=rows)

@app.route("/entree/new", methods=["GET","POST"])
def add_entree():
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        description = request.form.get("description","").strip()
        if montant <= 0 or not description:
            flash("Montant/description invalides.", "danger")
            return render_template("add_entree.html")
        date_enregistrement = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO entrees (montant, description, date_enregistrement) VALUES (?,?,?)",
                    (montant, description, date_enregistrement))
        conn.commit()
        conn.close()
        flash("Entrée ajoutée.", "success")
        return redirect(url_for("entrees"))
    return render_template("add_entree.html")

@app.route("/entree/edit/<int:entree_id>", methods=["GET","POST"])
def edit_entree(entree_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM entrees WHERE id=?", (entree_id,))
    e = cur.fetchone()
    if not e:
        conn.close()
        flash("Entrée introuvable.", "warning")
        return redirect(url_for("entrees"))
    if request.method == "POST":
        try:
            montant = float(request.form.get("montant","0"))
        except:
            montant = 0
        description = request.form.get("description","").strip()
        if montant <= 0 or not description:
            flash("Montant/description invalides.", "danger")
            return render_template("edit_entree.html", e=e)
        cur.execute("UPDATE entrees SET montant=?, description=? WHERE id=?", (montant, description, entree_id))
        conn.commit()
        conn.close()
        flash("Entrée modifiée.", "success")
        return redirect(url_for("entrees"))
    conn.close()
    return render_template("edit_entree.html", e=e)

@app.route("/entree/delete/<int:entree_id>", methods=["POST"])
def delete_entree(entree_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM entrees WHERE id=?", (entree_id,))
    conn.commit()
    conn.close()
    flash("Entrée supprimée.", "success")
    return redirect(url_for("entrees"))

# ✅ Appel immédiat au démarrage, que ce soit avec Flask, Gunicorn ou autre
init_db()

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.run(debug=True)
