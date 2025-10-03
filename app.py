from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
import re
import pymysql
from pymysql.err import IntegrityError
from datetime import datetime, timedelta, date  # 🔹 Import necesario
import calendar
import os
from werkzeug.utils import secure_filename
import pymysql.cursors
from flask_apscheduler import APScheduler   # 🔹 Para programar tareas automáticas
import smtplib                              # 🔹 Para enviar correos
from email.mime.text import MIMEText        # 🔹 Formato del correo
from dotenv import load_dotenv

# Inicializa la aplicación de Flask
app = Flask(__name__)
app.secret_key = "una_clave_secreta_muy_larga_y_segura"

# --- CONFIGURACIÓN PARA SUBIDA DE DOCUMENTOS ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Crea carpeta si no existe
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "html"}


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT")),
        cursorclass=pymysql.cursors.DictCursor
    )

# --- RUTAS DE LA APLICACIÓN ---
@app.route("/")
def index():
    user_name = session.get("user_name")
    user_email = session.get("user_email")
    return render_template("index.html", user_name=user_name, user_email=user_email)

@app.route("/rcp")
def rcp():
    user_name = session.get("user_name")
    user_email = session.get("user_email")
    return render_template("rcp.html", user_name=user_name, user_email=user_email)

@app.route("/consejos_salud")
def consejos_salud():
    user_name = session.get("user_name")
    user_email = session.get("user_email")
    return render_template("consejos_salud.html", user_name=user_name, user_email=user_email)


@app.route("/sesion", methods=["GET", "POST"])
def sesion():
    if request.method == "POST":
        documento = request.form["document_number"]
        contrasena = request.form["password"]

        try:
            connection = get_connection()
            with connection.cursor() as cursor:
                # 🔹 Incluimos rol y medico_id
                sql = "SELECT id, nombre, correo, documento, rol, medico_id FROM usuarios WHERE documento = %s AND contrasena = %s"
                cursor.execute(sql, (documento, contrasena))
                user = cursor.fetchone()

                if user:
                    # 🔹 Guardamos todos los datos en sesión
                    session["usuario_id"] = user["id"]
                    session["user_name"] = user["nombre"]
                    session["user_email"] = user["correo"]
                    session["documento"] = user["documento"]  
                    session["rol"] = user["rol"]               # 👈 guardamos rol
                    session["medico_id"] = user.get("medico_id")  # 👈 guardamos id del médico (si aplica)

                    flash("¡Inicio de sesión exitoso!", "success")

                    # 🔹 Redirección según rol
                    if user["rol"] == "medico":
                        return redirect(url_for("panel_medico"))
                    elif user["rol"] == "admin":
                        return redirect(url_for("admin_panel"))  # 🔹 futuro panel admin
                    else:
                        return redirect(url_for("index"))
                else:
                    flash("Número de documento o contraseña incorrectos.", "error")
                    return redirect(url_for("sesion"))

        except Exception as e:
            print(f"❌ Error al iniciar sesión: {e}")
            flash(f"Ocurrió un error al iniciar sesión: {e}", "error")
        finally:
            connection.close()

    return render_template("sesion.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            nombre = request.form["nombre"]
            tipo_documento = request.form["tipo_documento"]
            documento = request.form["documento"]
            correo = request.form["correo"]
            contrasena = request.form["contrasena"]
            telefono = request.form["telefono"]
            direccion = request.form["direccion"]
            fecha_nacimiento = request.form["fecha_nacimiento"]
            genero = request.form["genero"]
            ciudad = request.form["ciudad"]
            afiliado = request.form["afiliado"]

            connection = get_connection()
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO usuarios (
                        nombre, tipo_documento, documento, correo,
                        contrasena, telefono, direccion,
                        fecha_nacimiento, genero, ciudad, afiliado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (nombre, tipo_documento, documento, correo,
                           contrasena, telefono, direccion,
                           fecha_nacimiento, genero, ciudad, afiliado)

                cursor.execute(sql, valores)
                connection.commit()
                nuevo_id = cursor.lastrowid
            connection.close()

            # 🔹 Guardamos datos en sesión
            session["usuario_id"] = nuevo_id
            session["user_name"] = nombre
            session["user_email"] = correo
            session["documento"] = documento  # 👈 muy importante
            flash("¡Registro completado con éxito!", "success")
            return redirect(url_for("confirmacion"))

        except pymysql.err.IntegrityError as err:
            print(f"❌ Error de integridad: {err}")
            flash("Correo o documento ya están registrados.", "error")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            flash(f"Ocurrió un error: {e}", "error")
        return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/confirmacion")
def confirmacion():
    user_name = session.get("user_name")
    return render_template("confirmacion.html", user_name=user_name)


@app.route("/probar_conexion")
def probar_conexion():
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            resultado = cursor.fetchone()
        connection.close()
        return jsonify({"conexion": "exitosa", "base_de_datos": resultado})
    except Exception as e:
        return jsonify({"conexion": "fallida", "error": str(e)})


@app.route("/logout")
def logout():
    session.pop("usuario_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)
    session.pop("rol", None)         
    session.pop("medico_id", None)   
    session.pop("documento", None)
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("index"))


@app.route("/agendar_cita")
def agendar_cita():
    return render_template("agendar_cita.html",
                           user_name=session.get("user_name"),
                           user_email=session.get("user_email"))

@app.route("/citas", methods=["GET", "POST"])
def citas():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("sesion"))

    mensaje = None
    horarios_disponibles = []
    especialidades = []
    fecha_seleccionada = request.args.get("fecha")

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM especialidades")
            especialidades = cursor.fetchall()
        connection.close()
    except Exception as e:
        print("❌ Error cargando datos:", e)
        mensaje = "Error cargando información."

    if request.method == "POST":
        usuario_id = session["usuario_id"]
        nombre_paciente = session["user_name"]

        # 🔹 Intentamos obtener el documento de la sesión
        documento = session.get("documento")

        # 🔹 Si no está en sesión, lo sacamos de la base de datos
        if not documento:
            try:
                connection = get_connection()
                with connection.cursor() as cursor:
                    cursor.execute("SELECT documento FROM usuarios WHERE id = %s", (usuario_id,))
                    result = cursor.fetchone()
                    if result:
                        documento = result["documento"]
                        session["documento"] = documento  # lo volvemos a guardar en sesión
                connection.close()
            except Exception as e:
                print(f"❌ Error recuperando documento: {e}")
                documento = "SIN-DOC"  # fallback para no romper

        fecha = request.form["fecha"]
        hora = request.form["hora"]
        especialidad_id = request.form["especialidad"]
        medico_id = request.form["medico_id"]
        tipo_cita = request.form["tipo_cita"]  # 🔹 Nuevo campo

        try:
            connection = get_connection()
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id FROM citas
                    WHERE fecha = %s AND hora = %s AND medico_id = %s
                """, (fecha, hora, medico_id))
                existe = cursor.fetchone()

                if existe:
                    flash("⚠️ La cita no se pudo agendar porque la hora ya está ocupada con este médico. Selecciona otra.", "warning")
                    return redirect(url_for("citas", fecha=fecha))

                # 🔹 Insert con tipo_cita incluido
                sql_cita = """
                    INSERT INTO citas (usuario_id, nombre_paciente, documento, correo, fecha, hora, especialidad_id, medico_id, estado, tipo_cita)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (
                    usuario_id, nombre_paciente, documento, session["user_email"],
                    fecha, hora, especialidad_id, medico_id, "Pendiente", tipo_cita
                )
                cursor.execute(sql_cita, valores)

                connection.commit()
            connection.close()

            flash("✅ ¡Cita agendada correctamente! Revisa tu historial.", "success")
            return redirect(url_for("historial_citas"))

        except Exception as e:
            print(f"❌ Error al agendar cita: {e}")
            flash("⚠️ Hubo un error al intentar agendar la cita.", "error")

    return render_template(
        "citas.html",
        user_name=session.get("user_name"),
        user_email=session.get("user_email"),
        horarios=horarios_disponibles,
        mensaje=mensaje,
        fecha_seleccionada=fecha_seleccionada,
        especialidades=especialidades
    )


@app.route("/get_medicos/<int:especialidad_id>")
def get_medicos(especialidad_id):
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, nombre FROM medicos WHERE especialidad_id = %s", (especialidad_id,))
            medicos = cursor.fetchall()
        connection.close()
        return jsonify(medicos)
    except Exception as e:
        print("❌ Error al obtener médicos:", e)
        return jsonify([])

# 🔹 Obtener horarios disponibles dinámicamente
@app.route("/get_horarios/<int:medico_id>/<fecha>")
def get_horarios(medico_id, fecha):
    try:
        inicio = datetime.strptime("06:40", "%H:%M")
        fin = datetime.strptime("18:00", "%H:%M")
        delta = timedelta(minutes=20)

        horarios_totales = []
        hora_actual = inicio
        while hora_actual <= fin:
            horarios_totales.append(hora_actual.strftime("%H:%M"))
            hora_actual += delta

        # 👉 Consultar ocupados en la BD (excepto canceladas)
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT TIME_FORMAT(hora, '%%H:%%i') AS hora 
                FROM citas 
                WHERE medico_id = %s AND fecha = %s 
                AND estado != 'Cancelada'
            """, (medico_id, fecha))
            ocupados = [row["hora"] for row in cursor.fetchall()]
        connection.close()

        # 👉 Filtrar los que ya están ocupados
        disponibles = [h for h in horarios_totales if h not in ocupados]

        # 👉 Filtrar los que ya pasaron si la fecha es hoy
        fecha_consulta = datetime.strptime(fecha, "%Y-%m-%d").date()
        hoy = datetime.now().date()
        if fecha_consulta == hoy:
            hora_actual = datetime.now().strftime("%H:%M")
            disponibles = [h for h in disponibles if h > hora_actual]

        return jsonify(disponibles)

    except Exception as e:
        print("❌ Error al obtener horarios:", e)
        return jsonify([])



@app.route("/historial_citas")
def historial_citas():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("sesion"))

    usuario_id = session["usuario_id"]

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            sql = """
            SELECT c.id,
                   c.nombre_paciente,
                   c.documento,
                   c.correo,
                   e.nombre AS especialidad,
                   m.nombre AS medico,
                   c.fecha,
                   DATE_FORMAT(c.hora, '%%h:%%i %%p') AS hora,
                   c.estado,
                   c.tipo_cita   -- 🔹 Nuevo campo
            FROM citas c
            JOIN especialidades e ON c.especialidad_id = e.id
            JOIN medicos m ON c.medico_id = m.id
            WHERE c.usuario_id = %s
            ORDER BY c.fecha DESC, c.hora DESC
            """
            cursor.execute(sql, (usuario_id,))
            citas = cursor.fetchall()
        connection.close()
        return render_template("historial.html", citas=citas)
    except Exception as e:
        print("❌ Error cargando historial:", e)
        return render_template("historial.html", citas=[])


@app.route("/cancelar_cita/<int:cita_id>", methods=["POST"])
def cancelar_cita(cita_id):
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("sesion"))

    usuario_id = session["usuario_id"]

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            # Verificar que la cita exista y pertenezca al usuario
            cursor.execute("SELECT usuario_id FROM citas WHERE id = %s", (cita_id,))
            cita = cursor.fetchone()

            if not cita:
                flash("⚠️ La cita no existe.", "error")
                return redirect(url_for("historial_citas"))

            if cita["usuario_id"] != usuario_id:
                flash("No tienes permiso para cancelar esta cita.", "error")
                return redirect(url_for("historial_citas"))

            # Marcar cita como cancelada
            cursor.execute("UPDATE citas SET estado = 'Cancelada' WHERE id = %s", (cita_id,))
            connection.commit()

            flash("❌ La cita fue cancelada y el horario quedó libre.", "success")

        connection.close()
    except Exception as e:
        print(f"❌ Error al cancelar cita: {e}")
        flash("Hubo un error al cancelar la cita.", "error")

    return redirect(url_for("historial_citas"))


# --- PERFIL DE USUARIO ---
@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para ver tu perfil.", "error")
        return redirect(url_for("sesion"))

    usuario_id = session["usuario_id"]

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            if request.method == "POST":
                # 🔹 Capturamos los datos del formulario
                nombre = request.form["nombre"]
                tipo_documento = request.form["tipo_documento"]
                documento = request.form["documento"]
                correo = request.form["correo"]
                telefono = request.form["telefono"]
                direccion = request.form["direccion"]
                fecha_nacimiento = request.form["fecha_nacimiento"]
                genero = request.form["genero"]
                ciudad = request.form["ciudad"]
                afiliado = request.form["afiliado"]

                sql_update = """
                    UPDATE usuarios 
                    SET nombre=%s, tipo_documento=%s, documento=%s, correo=%s, 
                        telefono=%s, direccion=%s, fecha_nacimiento=%s, 
                        genero=%s, ciudad=%s, afiliado=%s
                    WHERE id=%s
                """
                valores = (nombre, tipo_documento, documento, correo, telefono,
                           direccion, fecha_nacimiento, genero, ciudad, afiliado, usuario_id)

                cursor.execute(sql_update, valores)
                connection.commit()

                # 🔹 Actualizamos la sesión
                session["user_name"] = nombre
                session["user_email"] = correo
                session["documento"] = documento

                flash("✅ Perfil actualizado con éxito.", "success")

            # 🔹 Siempre traemos la info actualizada
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            usuario = cursor.fetchone()
        connection.close()

        return render_template("perfil.html", usuario=usuario)

    except Exception as e:
        print(f"❌ Error en perfil: {e}")
        flash("Ocurrió un error al cargar el perfil.", "error")
        return redirect(url_for("index"))

@app.route("/editar_perfil", methods=["GET", "POST"])
def editar_perfil():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("sesion"))

    usuario_id = session["usuario_id"]
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            if request.method == "POST":
                nombre = request.form["nombre"]
                documento = request.form["documento"]
                telefono = request.form["telefono"]
                direccion = request.form["direccion"]
                ciudad = request.form["ciudad"]
                correo = request.form["correo"]

                try:
                    sql = """
                        UPDATE usuarios 
                        SET nombre=%s, documento=%s, telefono=%s, direccion=%s, ciudad=%s, correo=%s
                        WHERE id=%s
                    """
                    cursor.execute(sql, (nombre, documento, telefono, direccion, ciudad, correo, usuario_id))
                    connection.commit()

                    # 🔹 Actualizamos sesión
                    session["user_name"] = nombre
                    session["user_email"] = correo
                    session["documento"] = documento

                    flash("✅ Perfil actualizado con éxito.", "success")
                    return redirect(url_for("perfil"))

                except IntegrityError as e:
                    # 🔹 Detectar cuál campo está duplicado
                    error_str = str(e).lower()
                    if "documento" in error_str:
                        flash("⚠️ El número de documento ya está registrado por otro usuario.", "error")
                    elif "correo" in error_str:
                        flash("⚠️ El correo ya está registrado por otro usuario.", "error")
                    elif "telefono" in error_str:
                        flash("⚠️ El teléfono ya está registrado por otro usuario.", "error")
                    else:
                        flash("⚠️ Ya existe un dato duplicado en tu perfil.", "error")
                    return redirect(url_for("editar_perfil"))

            # GET → mostrar datos
            cursor.execute("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))
            usuario = cursor.fetchone()

    except Exception as e:
        print(f"❌ Error en editar_perfil: {e}")
        flash("Ocurrió un error al actualizar el perfil.", "error")
        return redirect(url_for("perfil"))
    finally:
        connection.close()

    return render_template("editar_perfil.html", usuario=usuario)


from datetime import date

@app.route("/panel_medico")
def panel_medico():
    if "usuario_id" not in session or session.get("rol") != "medico":
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("sesion"))

    hoy = date.today()
    medico_id = session.get("medico_id")

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            # 🔹 Citas de hoy
            cursor.execute("""
                SELECT c.id,
                       c.nombre_paciente,
                       c.documento,
                       u.tipo_documento,
                       c.fecha,
                       DATE_FORMAT(c.hora, '%%h:%%i %%p') AS hora,
                       c.estado,
                       c.notas,
                       c.tipo_cita,
                       u.correo AS correo_paciente
                FROM citas c
                JOIN usuarios u ON c.documento = u.documento
                WHERE c.medico_id = %s AND c.fecha = %s
                ORDER BY c.hora ASC
            """, (medico_id, hoy))
            citas_hoy = cursor.fetchall()

            # 🔹 Citas futuras
            cursor.execute("""
                SELECT c.id,
                       c.nombre_paciente,
                       c.documento,
                       u.tipo_documento,
                       c.fecha,
                       DATE_FORMAT(c.hora, '%%h:%%i %%p') AS hora,
                       c.estado,
                       c.notas,
                       c.tipo_cita,
                       u.correo AS correo_paciente
                FROM citas c
                JOIN usuarios u ON c.documento = u.documento
                WHERE c.medico_id = %s AND c.fecha > %s
                ORDER BY c.fecha, c.hora ASC
            """, (medico_id, hoy))
            citas_futuras = cursor.fetchall()

        connection.close()

        return render_template("panel_medico.html",
                               nombre_medico=session["user_name"],
                               citas_hoy=citas_hoy,
                               citas_futuras=citas_futuras)
    
    except Exception as e:
        print("❌ Error en panel_medico:", e)
        flash("Ocurrió un error al cargar el panel del médico.", "error")
        return redirect(url_for("index"))


@app.route("/historial_medico")
def historial_medico():
    if "usuario_id" not in session or session.get("rol") != "medico":
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("sesion"))

    medico_id = session.get("medico_id")

    # 🔹 Parámetros GET
    mes = request.args.get("mes", "actual")  # puede ser "actual", "todas" o un número
    documento = request.args.get("documento")
    tipo_doc = request.args.get("tipo_doc")
    scope = request.args.get("scope", "mias")
    hoy = date.today()
    anio = hoy.year

    try:
        # ==============================
        # 🔹 Filtro de fechas según opción
        # ==============================
        if mes == "actual":
            condicion_fecha = "YEAR(c.fecha) = %s AND MONTH(c.fecha) = %s"
            params_fecha = [anio, hoy.month]
            titulo_mes = f"Citas del mes actual ({calendar.month_name[hoy.month]} {anio})"

        elif mes == "todas":
            condicion_fecha = "1=1"  # no filtra por fecha
            params_fecha = []
            titulo_mes = "Historial completo de citas"

        else:
            # Si viene un número de mes (ej: "9" → septiembre)
            try:
                mes_int = int(mes)
                condicion_fecha = "YEAR(c.fecha) = %s AND MONTH(c.fecha) = %s"
                params_fecha = [anio, mes_int]
                titulo_mes = f"Citas de {calendar.month_name[mes_int]} {anio}"
            except ValueError:
                condicion_fecha = "1=1"
                params_fecha = []
                titulo_mes = "Historial completo de citas"

        # ==============================
        # 🔹 Construcción de la consulta
        # ==============================
        connection = get_connection()
        with connection.cursor() as cursor:
            if scope == "mias":
                sql = f"""
                    SELECT c.id, u.nombre AS nombre_paciente, u.tipo_documento AS tipo_doc, 
                           u.documento, c.fecha, DATE_FORMAT(c.hora, '%%H:%%i') AS hora, 
                           c.estado
                    FROM citas c
                    JOIN usuarios u ON c.usuario_id = u.id
                    WHERE {condicion_fecha}
                      AND c.medico_id = %s
                """
                params = params_fecha + [medico_id]

                # 🔹 Validación documento
                if documento and not tipo_doc:
                    flash("Debe seleccionar el tipo de documento para la búsqueda.", "error")
                    return redirect(url_for("historial_medico"))

                if documento and tipo_doc:
                    sql += " AND u.documento = %s AND u.tipo_documento = %s"
                    params.extend([documento, tipo_doc])

            elif scope == "todas":
                sql = f"""
                    SELECT c.id, u.nombre AS nombre_paciente, u.tipo_documento AS tipo_doc,
                           u.documento, c.fecha, DATE_FORMAT(c.hora, '%%H:%%i') AS hora, 
                           c.estado, m.nombre AS medico
                    FROM citas c
                    JOIN usuarios u ON c.usuario_id = u.id
                    JOIN medicos m ON c.medico_id = m.id
                    WHERE {condicion_fecha}
                """
                params = params_fecha

                if documento and not tipo_doc:
                    flash("Debe seleccionar el tipo de documento para la búsqueda.", "error")
                    return redirect(url_for("historial_medico"))

                if documento and tipo_doc:
                    sql += " AND u.documento = %s AND u.tipo_documento = %s"
                    params.extend([documento, tipo_doc])

            sql += " ORDER BY c.fecha DESC, c.hora DESC"
            cursor.execute(sql, tuple(params))
            citas_pasadas = cursor.fetchall()

        connection.close()

        # 🔹 Formatear tipo_doc
        for cita in citas_pasadas:
            if cita.get("tipo_doc"):
                cita["tipo_doc"] = cita["tipo_doc"].upper()
            else:
                cita["tipo_doc"] = ""

        return render_template(
            "historial_medico.html",
            citas_pasadas=citas_pasadas,
            titulo_mes=titulo_mes,
            scope=scope,
            documento=documento,
            tipo_doc=tipo_doc,
            mes=mes
        )

    except Exception as e:
        print("❌ Error en historial_medico:", e)
        flash("Ocurrió un error al cargar el historial.", "error")
        return redirect(url_for("panel_medico"))

# --- ACTUALIZAR ESTADO DE LA CITA ---
@app.route("/actualizar_estado/<int:cita_id>", methods=["POST"])
def actualizar_estado(cita_id):
    if "usuario_id" not in session or session.get("rol") != "medico":
        flash("Acceso no autorizado.", "error")
        return redirect(url_for("sesion"))

    nuevo_estado = request.form.get("estado")

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            sql = "UPDATE citas SET estado = %s WHERE id = %s"
            cursor.execute(sql, (nuevo_estado, cita_id))
            connection.commit()
        connection.close()

        flash("✅ Estado de la cita actualizado correctamente.", "success")
    except Exception as e:
        print(f"❌ Error al actualizar estado: {e}")
        flash("Ocurrió un error al actualizar el estado de la cita.", "error")

    return redirect(url_for("panel_medico"))


@app.route("/documento_medico")
def documento_medico():
    if "usuario_id" not in session or session.get("rol") != "paciente":
        flash("Debes iniciar sesión como paciente para acceder a tus documentos médicos.", "error")
        return redirect(url_for("sesion"))

    usuario_id = session["usuario_id"]
    documentos_citas = []
    documentos_independientes = []

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            # 🔹 Documentos ligados a citas
            sql_citas = """
                SELECT d.id, d.nombre, d.tipo, d.archivo, d.subido_por, d.fecha_subida,
                       c.fecha AS fecha_cita, c.hora, c.especialidad_id
                FROM documentos_medicos d
                LEFT JOIN citas c ON d.cita_id = c.id
                WHERE d.usuario_id = %s AND d.cita_id IS NOT NULL
                ORDER BY d.fecha_subida DESC
            """
            cursor.execute(sql_citas, (usuario_id,))
            documentos_citas = cursor.fetchall()

            # 🔹 Documentos independientes
            sql_indep = """
                SELECT d.id, d.nombre, d.tipo, d.archivo, d.subido_por, d.fecha_subida
                FROM documentos_medicos d
                WHERE d.usuario_id = %s AND d.cita_id IS NULL
                ORDER BY d.fecha_subida DESC
            """
            cursor.execute(sql_indep, (usuario_id,))
            documentos_independientes = cursor.fetchall()

        connection.close()

    except Exception as e:
        print("❌ Error al obtener documentos del paciente:", e)
        flash("No se pudieron cargar tus documentos médicos.", "error")

    return render_template(
        "documento_medico.html",
        documentos_citas=documentos_citas,
        documentos_independientes=documentos_independientes
    )


@app.route("/documentos_paciente", methods=["GET"])
def documentos_paciente():
    documento = request.args.get("documento")
    tipo_documento = request.args.get("tipo_documento")

    paciente = None
    documentos_citas = []
    documentos_independientes = []

    if documento and tipo_documento:
        connection = get_connection()
        try:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                # 🔹 Obtener paciente
                cursor.execute("""
                    SELECT * FROM usuarios 
                    WHERE tipo_documento = %s AND documento = %s
                """, (tipo_documento, documento))
                paciente = cursor.fetchone()

                if paciente:
                    paciente_id = paciente["id"]

                    # 🔹 Documentos ligados a citas
                    sql_citas = """
                        SELECT d.*, u.nombre AS subido_por
                        FROM documentos_medicos d
                        LEFT JOIN usuarios u ON u.id = d.medico_id
                        WHERE d.usuario_id = %s AND d.cita_id IS NOT NULL
                        ORDER BY d.fecha_subida DESC
                    """
                    cursor.execute(sql_citas, (paciente_id,))
                    documentos_citas = cursor.fetchall()

                    # 🔹 Documentos independientes (no ligados a cita)
                    sql_indep = """
                        SELECT d.*, u.nombre AS subido_por
                        FROM documentos_medicos d
                        LEFT JOIN usuarios u ON u.id = d.medico_id
                        WHERE d.usuario_id = %s AND d.cita_id IS NULL
                        ORDER BY d.fecha_subida DESC
                    """
                    cursor.execute(sql_indep, (paciente_id,))
                    documentos_independientes = cursor.fetchall()

        finally:
            connection.close()

    return render_template(
        "documentos_paciente.html",
        paciente=paciente,
        documentos_citas=documentos_citas,
        documentos_independientes=documentos_independientes
    )



@app.route("/subir_documento_paciente", methods=["GET", "POST"])
def subir_documento_paciente():
    if "usuario_id" not in session or session.get("rol") != "paciente":
        flash("Acceso no autorizado", "error")
        return redirect(url_for("sesion"))

    if request.method == "POST":
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo.", "error")
            return redirect(url_for("documento_medico"))

        archivo = request.files["archivo"]
        nombre_doc = request.form.get("nombre", "Documento Médico")
        tipo_doc = request.form.get("tipo", "Otro")

        if archivo.filename == "":
            flash("⚠️ Nombre de archivo vacío.", "error")
            return redirect(url_for("documento_medico"))

        if archivo and allowed_file(archivo.filename):
            try:
                filename = secure_filename(archivo.filename)
                ruta_guardado = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                archivo.save(ruta_guardado)

                connection = get_connection()
                with connection.cursor() as cursor:
                    sql = """
                        INSERT INTO documentos_medicos 
                        (nombre, tipo, archivo, subido_por, usuario_id, medico_id, cita_id, fecha_subida)
                        VALUES (%s, %s, %s, %s, %s, NULL, NULL, NOW())
                    """
                    valores = (
                        nombre_doc,
                        tipo_doc,
                        filename,
                        session["user_name"],   # Paciente que sube el archivo
                        session["usuario_id"]
                    )
                    cursor.execute(sql, valores)
                    connection.commit()
                connection.close()

                flash("✅ Documento subido correctamente.", "success")
            except Exception as e:
                print("❌ Error al subir documento:", e)
                flash("Ocurrió un error al subir el documento.", "error")
        else:
            flash("Formato de archivo no permitido. Usa PDF, JPG, JPEG o PNG.", "error")

        return redirect(url_for("documento_medico"))

    # GET → Mostrar formulario
    return render_template("subir_documento_paciente.html")


@app.route("/subir_documento/<int:cita_id>", methods=["GET", "POST"])
def subir_documento(cita_id):
    if "usuario_id" not in session or session.get("rol") != "medico":
        flash("Acceso no autorizado", "error")
        return redirect(url_for("sesion"))

    if request.method == "GET":
        return render_template("subir_documento.html", cita_id=cita_id)

    if "archivo" not in request.files:
        flash("No se seleccionó ningún archivo.", "error")
        return redirect(url_for("panel_medico"))

    archivo = request.files["archivo"]
    nombre_doc = request.form.get("nombre", "Documento Médico")
    tipo_doc = request.form.get("tipo", "Otro")

    if archivo.filename == "":
        flash("⚠️ Nombre de archivo vacío.", "error")
        return redirect(url_for("panel_medico"))

    if not (archivo and allowed_file(archivo.filename)):
        flash("Formato de archivo no permitido. Usa PDF, JPG, JPEG o PNG.", "error")
        return redirect(url_for("panel_medico"))

    # Guardar archivo con nombre único (timestamp + nombre seguro)
    try:
        orig_filename = secure_filename(archivo.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_{orig_filename}"
        ruta_guardado = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        archivo.save(ruta_guardado)
    except Exception as e:
        print("❌ Error guardando archivo en disco:", e)
        flash("Ocurrió un error al guardar el archivo.", "error")
        return redirect(url_for("panel_medico"))

    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            # Intentamos obtener usuario_id desde la cita
            cursor.execute("SELECT usuario_id, documento FROM citas WHERE id = %s", (cita_id,))
            cita = cursor.fetchone()
            paciente_id = None

            if cita:
                paciente_id = cita.get("usuario_id") or None

                # Si la cita no tiene usuario_id pero sí documento, buscamos el id en usuarios
                if not paciente_id and cita.get("documento"):
                    cursor.execute("SELECT id FROM usuarios WHERE documento = %s", (cita["documento"],))
                    u = cursor.fetchone()
                    if u:
                        paciente_id = u["id"]

            # Fallback: intentar con el documento en sesión (si existe)
            if not paciente_id:
                documento_sesion = session.get("documento")
                if documento_sesion:
                    cursor.execute("SELECT id FROM usuarios WHERE documento = %s", (documento_sesion,))
                    u2 = cursor.fetchone()
                    if u2:
                        paciente_id = u2["id"]

            if not paciente_id:
                raise Exception("No se pudo determinar el paciente (usuario_id) asociado a la cita.")

            # Insertar registro incluyendo el 'tipo'
            sql = """
                INSERT INTO documentos_medicos
                (nombre, tipo, archivo, subido_por, usuario_id, medico_id, cita_id, fecha_subida)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """
            valores = (
                nombre_doc,
                tipo_doc,
                filename,
                session.get("user_name", "medico"),
                paciente_id,
                session.get("medico_id"),
                cita_id
            )
            cursor.execute(sql, valores)
            connection.commit()

        flash("✅ Documento subido correctamente.", "success")

    except Exception as e:
        print("❌ Error al subir documento:", e)
        flash(f"Ocurrió un error al subir el documento: {e}", "error")

    finally:
        if connection:
            connection.close()

    return redirect(url_for("panel_medico"))


# app.py
@app.route("/subir_documento_medico", methods=["GET", "POST"])
def subir_documento_medico():
    if request.method == "POST":
        usuario_id = request.form.get("usuario_id")
        nombre = request.form.get("nombre")
        tipo = request.form.get("tipo")
        archivo = request.files.get("archivo")

        # Validación de campos
        if not usuario_id or not nombre or not tipo or not archivo:
            flash("Todos los campos son obligatorios.", "error")
            return redirect(request.url)

        try:
            usuario_id = int(usuario_id)  # ✅ Convertir a entero
        except ValueError:
            flash("ID de usuario inválido.", "error")
            return redirect(request.url)

        # Guardar archivo en servidor
        filename = secure_filename(archivo.filename)
        upload_path = os.path.join("uploads", filename)
        archivo.save(upload_path)

        # Obtener nombre del médico desde la sesión
        medico_nombre = session.get("user_name", "MedicoDesconocido")  

        # Guardar registro en DB
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                INSERT INTO documentos_medicos (usuario_id, nombre, tipo, archivo, fecha_subida, subido_por)
                VALUES (%s, %s, %s, %s, NOW(), %s)
                """
                cursor.execute(sql, (usuario_id, nombre, tipo, filename, medico_nombre))
            connection.commit()
            flash("Documento subido correctamente.", "success")
        except Exception as e:
            flash(f"Error al guardar en la base de datos: {str(e)}", "error")
        finally:
            connection.close()

        # Redirigir al listado de documentos del paciente
        return redirect(url_for("documentos_paciente", tipo_documento="CC", documento=""))

    # GET → mostrar formulario
    paciente_id = request.args.get("usuario_id")
    if not paciente_id:
        flash("No se recibió el ID del paciente.", "error")
        return redirect(url_for("panel_medico"))

    return render_template("subir_documento_medico.html", paciente_id=paciente_id)




# --- SERVIR ARCHIVOS SUBIDOS ---
from flask import send_from_directory

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# --- admin panel ---

@app.route("/admin_panel")
def admin_panel():
    if session.get("rol") != "admin":
        flash("No tienes permiso para acceder a esta página.", "error")
        return redirect(url_for("index"))
    return render_template("admin_panel.html")

# Panel de citas (solo admin)
# ===============================
# 🔹 Gestión de citas (ADMIN)
# ===============================
@app.route("/admin/citas")
def admin_citas():
    if session.get("rol") != "admin":
        flash("No tienes permiso para acceder a esta página.", "error")
        return redirect(url_for("index"))

    connection = get_connection()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT c.id,
                   COALESCE(p.nombre, c.nombre_paciente) AS paciente,
                   COALESCE(u_med.nombre, 'No asignado') AS medico,
                   e.nombre AS especialidad,
                   c.fecha,
                   DATE_FORMAT(c.hora, '%h:%i %p') AS hora,
                   c.estado,
                   c.tipo_cita
            FROM citas c
            LEFT JOIN usuarios p ON c.usuario_id = p.id
            LEFT JOIN medicos m ON c.medico_id = m.id
            LEFT JOIN usuarios u_med ON m.id = u_med.medico_id AND u_med.rol = 'medico'
            LEFT JOIN especialidades e ON m.especialidad_id = e.id
            ORDER BY 
                CASE WHEN c.fecha >= CURDATE() THEN 0 ELSE 1 END,
                c.fecha ASC,
                c.hora ASC
        """)
        citas = cursor.fetchall()
    
    connection.close()
    return render_template("admin_citas.html", citas=citas)


# 🔹 Nueva ruta para actualizar estado como admin
@app.route("/admin/actualizar_estado/<int:cita_id>", methods=["POST"])
def admin_actualizar_estado(cita_id):
    if session.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("index"))

    nuevo_estado = request.form.get("estado")

    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            sql = "UPDATE citas SET estado = %s WHERE id = %s"
            cursor.execute(sql, (nuevo_estado, cita_id))
            connection.commit()
        connection.close()

        flash("✅ Estado de la cita actualizado correctamente (Admin).", "success")
    except Exception as e:
        print(f"❌ Error al actualizar estado (Admin): {e}")
        flash("Ocurrió un error al actualizar el estado de la cita.", "error")

    return redirect(url_for("admin_citas"))



@app.route("/admin/medicos")
def gestion_medicos():
    if session.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("index"))

    connection = get_connection()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT 
                u.id AS usuario_id,
                u.nombre AS nombre_usuario,
                u.tipo_documento,
                u.documento,
                u.correo,
                u.telefono,
                m.id AS medico_id,
                e.nombre AS especialidad,
                m.disponible
            FROM usuarios u
            JOIN medicos m ON u.medico_id = m.id
            JOIN especialidades e ON m.especialidad_id = e.id
            WHERE u.rol = 'medico'
        """)
        medicos = cursor.fetchall()

    return render_template("medicos.html", medicos=medicos)



@app.route("/admin/medicos/editar/<int:medico_id>", methods=["GET", "POST"])
def editar_medico(medico_id):
    if session.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("index"))

    connection = get_connection()
    with connection.cursor() as cursor:

        # GET → obtener datos actuales
        cursor.execute("""
            SELECT 
                u.id AS usuario_id,
                u.nombre,
                u.tipo_documento,
                u.documento,
                u.correo,
                u.telefono,
                u.direccion,
                u.ciudad,
                u.fecha_nacimiento,
                u.genero,
                u.afiliado,
                m.id AS medico_id,
                m.especialidad_id,
                m.disponible
            FROM usuarios u
            JOIN medicos m ON u.medico_id = m.id
            WHERE m.id = %s
        """, (medico_id,))
        medico = cursor.fetchone()

        cursor.execute("SELECT id, nombre FROM especialidades")
        especialidades = cursor.fetchall()

        if request.method == "POST":
            nombre = request.form["nombre"]
            documento = request.form["documento"]  # ahora editable
            correo = request.form["correo"]
            telefono = request.form["telefono"]
            direccion = request.form["direccion"]
            ciudad = request.form["ciudad"]
            fecha_nacimiento = request.form["fecha_nacimiento"]
            genero = request.form["genero"]
            afiliado = request.form["afiliado"]
            especialidad_id = request.form["especialidad_id"]
            disponible = 1 if request.form.get("disponible") == "on" else 0

            # 🔹 Validación: edad >= 18
            if fecha_nacimiento:
                fecha_nac = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
                edad = (date.today() - fecha_nac).days // 365
                if edad < 18:
                    flash("El médico debe ser mayor de 18 años.", "error")
                    return redirect(url_for("editar_medico", medico_id=medico_id))

            # 🔹 Actualización tabla usuarios
            cursor.execute("""
                UPDATE usuarios
                SET nombre = %s,
                    documento = %s,
                    correo = %s,
                    telefono = %s,
                    direccion = %s,
                    ciudad = %s,
                    fecha_nacimiento = %s,
                    genero = %s,
                    afiliado = %s
                WHERE id = %s
            """, (
                nombre, documento, correo, telefono, direccion, ciudad,
                fecha_nacimiento, genero, afiliado, medico['usuario_id']
            ))

            # 🔹 Actualización tabla medicos (ahora también incluye nombre ✅)
            cursor.execute("""
                UPDATE medicos
                SET nombre = %s,
                    especialidad_id = %s,
                    disponible = %s
                WHERE id = %s
            """, (nombre, especialidad_id, disponible, medico_id))

            connection.commit()
            flash("Médico actualizado correctamente.", "success")
            return redirect(url_for("gestion_medicos"))

    return render_template("editar_medico.html", medico=medico, especialidades=especialidades)


@app.route("/admin/medicos/eliminar/<int:medico_id>")
def eliminar_medico(medico_id):
    if session.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("index"))

    connection = get_connection()
    with connection.cursor() as cursor:
        # 1. Eliminar usuarios vinculados al médico
        cursor.execute("DELETE FROM usuarios WHERE medico_id = %s", (medico_id,))

        # 2. Eliminar al médico
        cursor.execute("DELETE FROM medicos WHERE id = %s", (medico_id,))

        connection.commit()
        flash("Médico eliminado correctamente junto con su usuario.", "success")

    return redirect(url_for("gestion_medicos"))



@app.route("/admin/medicos/agregar", methods=["GET", "POST"])
def agregar_medico():
    if session.get("rol") != "admin":
        flash("Acceso denegado.", "error")
        return redirect(url_for("index"))

    connection = get_connection()
    with connection.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id, nombre FROM especialidades")
        especialidades = cursor.fetchall()

        if request.method == "POST":
            nombre = request.form["nombre"]
            tipo_documento = request.form["tipo_documento"]
            documento = request.form["documento"]
            correo = request.form["correo"]
            contrasena = request.form["contrasena"]  # texto plano
            telefono = request.form.get("telefono")
            direccion = request.form.get("direccion")
            ciudad = request.form.get("ciudad")
            fecha_nacimiento = request.form.get("fecha_nacimiento")
            genero = request.form.get("genero")
            afiliado = request.form.get("afiliado")
            especialidad_id = request.form["especialidad_id"]
            disponible = 1 if request.form.get("disponible") == "on" else 0

            # Validación edad >= 18
            from datetime import datetime, date
            fecha_nac = datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
            edad = (date.today() - fecha_nac).days // 365
            if edad < 18:
                flash("El médico debe ser mayor de 18 años.", "error")
                return redirect(url_for("agregar_medico"))

            # Insertar primero en medicos
            cursor.execute("""
                INSERT INTO medicos (nombre, especialidad_id, disponible)
                VALUES (%s, %s, %s)
            """, (nombre, especialidad_id, disponible))
            medico_id = cursor.lastrowid

            # Insertar en usuarios con el medico_id generado
            cursor.execute("""
                INSERT INTO usuarios (nombre, tipo_documento, documento, correo, contrasena,
                                      telefono, direccion, fecha_nacimiento, genero, ciudad, rol, afiliado, medico_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'medico', %s, %s)
            """, (nombre, tipo_documento, documento, correo, contrasena,
                  telefono, direccion, fecha_nacimiento, genero, ciudad, afiliado, medico_id))

            connection.commit()
            flash("Médico agregado correctamente.", "success")
            return redirect(url_for("gestion_medicos"))

    return render_template("agregar_medico.html", especialidades=especialidades)


# -------------------------
# Configuración SMTP
# -------------------------
SMTP_REMITENTE = "asistencia00medica99@gmail.com"
SMTP_PASSWORD_APP = "adgrnzzfjmfetxsm"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# -------------------------
# Función para enviar correos
# -------------------------
def enviar_recordatorio(to_email, subject, mensaje):
    try:
        msg = MIMEText(mensaje, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = SMTP_REMITENTE
        msg["To"] = to_email

        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_REMITENTE, SMTP_PASSWORD_APP)
        server.sendmail(SMTP_REMITENTE, [to_email], msg.as_string())
        server.quit()
        print(f"✅ Email enviado a {to_email}")
    except Exception as e:
        print("❌ Error enviando correo:", str(e))


# -------------------------
# Revisión automática de medicamentos
# -------------------------

def revisar_medicamentos():
    connection = get_connection()
    now = datetime.now()

    with connection.cursor() as cursor:
        # Eliminar medicamentos vencidos
        cursor.execute("DELETE FROM medicamentos WHERE fecha_fin < %s", (now.date(),))
        connection.commit()

        # Obtener medicamentos activos
        cursor.execute("""
            SELECT m.*, u.correo, u.nombre AS nombre_usuario
            FROM medicamentos m
            JOIN usuarios u ON m.usuario_id = u.id
        """)
        medicamentos = cursor.fetchall()

        for med in medicamentos:
            fecha_inicio = datetime.strptime(str(med["fecha_inicio"]), "%Y-%m-%d")
            fecha_fin = datetime.strptime(str(med["fecha_fin"]), "%Y-%m-%d") + timedelta(days=1)
            frecuencia = med["frecuencia"]
            ultimo = med.get("ultimo_recordatorio")

            # Solo si está dentro del rango de fechas
            if not (fecha_inicio <= now <= fecha_fin):
                continue

            enviar = False
            if not ultimo:
                # Primer recordatorio: enviar de inmediato
                enviar = True
            else:
                try:
                    ultimo_dt = datetime.strptime(str(ultimo), "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    ultimo_dt = datetime.strptime(str(ultimo), "%Y-%m-%d %H:%M:%S")
                
                if now >= ultimo_dt + timedelta(hours=frecuencia):
                    enviar = True

            if enviar:
                mensaje_recordatorio = f"""
🔔 MediAlert - Recordatorio de Medicación

Hola {med['nombre_usuario']} 👋

Es hora de tomar tu medicamento:
💊 {med['nombre']}
📋 Dosis: {med['dosis']}
⏰ Cada {frecuencia} horas
📅 Desde {med['fecha_inicio']} hasta {med['fecha_fin']}

¡No olvides tomarlo a tiempo!
Equipo MediAlert 💙
"""
                enviar_recordatorio(med["correo"], f"🔔 MediAlert - Recordatorio de Medicación: {med['nombre']}", mensaje_recordatorio)

                # Actualizar último envío
                cursor.execute("UPDATE medicamentos SET ultimo_recordatorio=%s WHERE id=%s", (now, med["id"]))
                connection.commit()

    connection.close()




# -------------------------
# APScheduler
# -------------------------
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Revisar medicamentos cada minuto
scheduler.add_job(id="revisar_meds", func=revisar_medicamentos, trigger="interval", minutes=1)

# -------------------------
# Rutas
# -------------------------
@app.route("/recordatorio")
def recordatorio():
    if "usuario_id" not in session:   # Validar sesión
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("sesion"))

    user_name = session.get("user_name")
    user_email = session.get("user_email")
    return render_template("recordatorio.html", user_name=user_name, user_email=user_email)



@app.route("/registrar_medicamento", methods=["POST"])
def registrar_medicamento():
    data = request.get_json()
    user_id = session.get("usuario_id", 1)
    now = datetime.now()

    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO medicamentos (usuario_id, nombre, dosis, frecuencia, fecha_inicio, fecha_fin, correo, ultimo_recordatorio)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            data["nombre"],
            data["dosis"],
            int(data["frecuencia"]),
            data["fecha_inicio"],
            data["fecha_fin"],
            data["correo"],
            now  # <-- Establecemos el primer recordatorio al registrar
        ))
        connection.commit()
    connection.close()

    # Enviar primer recordatorio inmediatamente
    mensaje_recordatorio = f"""
🔔 MediAlert - Recordatorio de Medicación

Hola {data.get('nombre_usuario', 'Usuario')} 👋

Es hora de tomar tu medicamento:
💊 {data['nombre']}
📋 Dosis: {data['dosis']}
⏰ Cada {data['frecuencia']} horas
📅 Desde {data['fecha_inicio']} hasta {data['fecha_fin']}

¡No olvides tomarlo a tiempo!
Equipo MediAlert 💙
"""
    enviar_recordatorio(data["correo"], f"🔔 MediAlert - Recordatorio de Medicación: {data['nombre']}", mensaje_recordatorio)

    return jsonify({"success": True, "message": "Medicamento registrado y primer recordatorio enviado"})




@app.route("/obtener_medicamentos", methods=["GET"])
def obtener_medicamentos():
    user_id = session.get("usuario_id", 1)
    connection = get_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM medicamentos WHERE usuario_id=%s", (user_id,))
        meds = cursor.fetchall()
    connection.close()
    return jsonify(meds)

@app.route("/api/send-email", methods=["POST"])
def api_send_email():
    try:
        data = request.get_json(force=True) or {}
        to_email = data.get("to")
        subject = data.get("subject", "🔔 MediAlert - Recordatorio de Medicación")
        mensaje = data.get("message", "")

        if not to_email:
            return jsonify({"success": False, "error": "Falta 'to' (correo destino)"}), 400

        enviar_recordatorio(to_email, subject, mensaje)
        return jsonify({"success": True, "message": f"Email enviado a {to_email}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/eliminar_medicamento/<int:med_id>", methods=["DELETE"])
def eliminar_medicamento(med_id):
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM medicamentos WHERE id=%s", (med_id,))
            connection.commit()
        connection.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})




# --- CHATBOT ---
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").lower()
    user_msg_clean = re.sub(r'[^\w\sáéíóúüñ]', '', user_msg)

    saludo_regex = r"h+o+l+a+|b+u+e+n+o*s* *d+í*a+s*|h+e+y+|q+u+é+ *t+a+l+"
    despedidas = ["adiós", "chao", "hasta luego", "nos vemos", "me voy", "bye"]
    malas_palabras = ["idiota", "imbécil", "estúpido", "mierda", "puta",
                      "malparido", "gonorrea", "fuck", "tonto", "pendejo", "culero"]

    emociones = {
        "triste": "Lamento que te sientas así. ¿Quieres hablar de eso o necesitas apoyo emocional?",
        "deprimido": "Estás pasando por un momento difícil. Habla con alguien de confianza o considera ayuda psicológica.",
        "ansioso": "Respira profundamente. Estás a salvo. ¿Quieres que te sugiera ejercicios de relajación?",
        "feliz": "¡Qué bueno! Me alegra saberlo. ¿Hay algo que quieras compartir?",
        "estresado": "Es importante tomar pausas. ¿Te gustaría recibir tips para reducir el estrés?",
        "solo": "No estás solo. Estoy aquí contigo, y puedes contarme lo que sientes.",
        "abrumado": "Tómate un momento para ti. Vamos paso a paso. ¿En qué puedo ayudarte?",
        "enojado": "Entiendo que estés molesto. Puedes hablar de ello o simplemente desahogarte aquí."
    }

    enfermedades = {
        "cabeza": "Podrías tomar paracetamol y descansar. Si persiste, consulta a un médico.",
        "fiebre": "Bebe líquidos, descansa y toma acetaminofén. Consulta si supera los 39°C.",
        "tos": "Hidrátate, evita el frío. Si es persistente, podría ser COVID u otra infección.",
        "gripa": "Descansa, toma líquidos y mantente abrigado.",
        "diarrea": "Hidrátate con suero oral. Consulta si persiste más de 2 días.",
        "náuseas": "Toma líquidos claros, evita alimentos pesados.",
        "mareo": "Puede deberse a estrés o baja presión. Reposa y evalúa.",
        "dolor abdominal": "Podría ser indigestión, gastritis u otros. Evita comidas pesadas.",
        "vómito": "Hidrátate con sorbos pequeños. Si hay sangre o persiste, consulta.",
        "asma": "Usa tu inhalador. Si no mejora, busca atención médica urgente.",
        "covid": "Si tienes fiebre, tos seca y fatiga, aíslate y hazte una prueba."
    }


    # --- Bienvenida con menú ---
    if re.search(saludo_regex, user_msg_clean) or user_msg_clean.strip() in ["menu", "ayuda", "inicio"]:
        reply = """
👋 ¡Hola, bienvenido a <b>Asistencia Médica J.A</b>!<br><br>
Antes de empezar recuerda:<br>
🔹 Si ya tienes cuenta → <a href="/sesion">Iniciar sesión</a><br>
🔹 Si no tienes cuenta → <a href="/register">Registrarse</a><br><br>
<b>Puedo ayudarte con las siguientes acciones:</b><br>
- 🗓️ <a href="/agendar_cita">Agendar una cita</a><br>
- 📑 <a href="/historial_citas">Ver historial de citas</a><br>
- 👤 <a href="/perfil">Ver perfil</a><br>
- 📂 <a href="/documento_medico">Ver documentos médicos</a><br>
- 💊 <a href="/recordatorio">Recordatorios de medicación</a><br>
- ❤️ <a href="/rcp">Información de RCP</a><br>
- 💡 <a href="/consejos_salud">Consejos de salud</a><br>
Escríbeme lo que necesites y te guiaré paso a paso.
"""
    elif any(p in user_msg for p in malas_palabras):
        reply = "🚫 <b>Por favor, mantén el respeto.</b>"
    elif any(d in user_msg for d in despedidas):
        reply = "👋 Cuídate mucho. ¡Hasta pronto!"
    elif "me pegaron" in user_msg or "me hicieron daño" in user_msg:
        reply = "⚠️ Lamento escuchar eso. Si estás en peligro busca ayuda urgente o llama a emergencias."
    elif "no quiero vivir" in user_msg or "quiero morir" in user_msg:
        reply = "💔 Siento que te sientas así. Habla con alguien de confianza o llama a una línea de ayuda de tu país."
    elif any(emo in user_msg for emo in emociones.keys()):
        reply = next(res for emo, res in emociones.items() if emo in user_msg)
    elif any(enf in user_msg for enf in enfermedades.keys()):
        reply = next(res for enf, res in enfermedades.items() if enf in user_msg)


    # --- Acciones con explicación ---
    elif "agendar" in user_msg and "cita" in user_msg:
        reply = """
✅ <b>Agendar una cita:</b><br>
1️⃣ Ingresa aquí → <a href="/citas">Agendar Cita</a><br>
2️⃣ Inicia sesión en tu cuenta (si no la tienes, regístrate).<br>
3️⃣ Completa el formulario con los datos solicitados.<br>
4️⃣ Revisa el estado en <a href="/historial_citas">Historial de Citas</a>.<br>
"""
    elif "historial" in user_msg or "citas" in user_msg:
        reply = """
📑 <b>Historial de Citas:</b><br>
Accede aquí → <a href="/historial_citas">Ver historial de citas</a><br>
Podrás ver tus citas confirmadas, canceladas o pendientes.<br>
"""
    elif "perfil" in user_msg:
        reply = """
👤 <b>Perfil de usuario:</b><br>
Accede aquí → <a href="/perfil">Ver perfil</a><br>
Desde tu perfil puedes actualizar tu información personal.<br>
"""
    elif "documento" in user_msg or "médico" in user_msg:
        reply = """
📂 <b>Documentos médicos:</b><br>
Accede aquí → <a href="/documento_medico">Ver documentos</a><br>
Encontrarás tus resultados, órdenes y archivos médicos.<br>
"""
    elif "medicación" in user_msg or "recordar" in user_msg:
        reply = """
💊 <b>Recordatorios de medicación:</b><br>
Accede aquí → <a href="/recordatorio">Recordatorio</a><br>
Puedes configurar aquí tus recordatorios de medicación.<br>
"""
    elif "rcp" in user_msg or "primeros auxilios" in user_msg:
        reply = """
❤️ <b>Información de RCP:</b><br>
Accede aquí → <a href="/rcp">rcp</a><br>
Puedes informarte aquí y salvar una vida.<br>
1️⃣ Comprueba si la persona responde y respira.<br>
2️⃣ Llama a emergencias.<br>
3️⃣ Si no respira, inicia compresiones torácicas (100-120/minuto).<br>
⚠️ Consulta la guía oficial o recibe capacitación en primeros auxilios.<br>
"""
    elif "consejo" in user_msg or "salud" in user_msg:
        reply = """
💡 <b>Consejos de salud:</b><br>
Accede aquí → <a href="consejos_salud">consejos de salud</a><br>
Encontraras aquí información muy útil.<br>
- Hidrátate 💧<br>
- Duerme 7-8 horas 😴<br>
- Haz ejercicio regularmente 🏃<br>
- Consume frutas y verduras 🍎🥦<br>
- Tómate pausas y gestiona el estrés 🌿<br>
"""
  
    elif "iniciar sesión" in user_msg or "login" in user_msg:
        reply = "🔑 Accede a tu cuenta aquí → <a href='/sesion'>Iniciar sesión</a>"
    elif "registrar" in user_msg or "crear cuenta" in user_msg:
        reply = "📝 Crea tu cuenta aquí → <a href='/register'>Registrarse</a>"
    else:
        reply = "🤔 No entendí bien. Escribe <b>'menu'</b> para ver todas las opciones disponibles."

    return jsonify({"reply": reply})


# Arranque de la app (modo debug para desarrollo)
if __name__ == "__main__":
    app.run(debug=True)