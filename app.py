from flask import Flask
from flask import render_template, redirect, request, session, url_for
from flask_mysqldb import MySQL
from datetime import datetime
import pymysql
from werkzeug.security import generate_password_hash


# INICIALIZACION DE LA APLICACION FLASK
app = Flask(__name__, template_folder="templates")
app.app_context().push()

# CONEXION A LA BASE DE DATOS
app.config["MYSQL_HOST"]="roundhouse.proxy.rlwy.net"
app.config["MYSQL_USER"]="root"
app.config["MYSQL_PASSWORD"]="zpghwZJfGhDNAuUSCjxLxfGwXgayuZpO"
app.config["MYSQL_DB"]="sm"
#app.config["MYSQL_CURSORCLASS"]="dictCursor"
mysql = MySQL(app)
app.config["SECRET_KEY"] = "1145"  # Define la clave secreta antes de acceder a la sesión

try:
    mysql.connection.ping(reconnect=True)
    print("Conexión exitosa a la base de datos")
except Exception as e:
    print("Error al conectar a la base de datos:", e)



#                             SM WEB

# MOSTRAR PANTALLA DE INICIO
@app.route("/")
def home():
    return render_template("index.html")

# FUNCION PARA LOS DOS TIPOS DE USUARIOS 
@app.route("/login", methods=["POST"])
def login():
    # INICIO DE SESION
    email = request.form['email']
    contraseña = request.form['contraseña']
    

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM login WHERE email = %s AND contraseña = %s", (email, contraseña))
    user = cur.fetchone()

    if user is not None:
        session['id'] = user[0]
        session['email'] = email
        session['name'] = user[1]
        session['surname'] = user[2]
        session['contraseña'] = user[4]
        cur.close()
        return redirect(url_for('inbox'))
    
    # Inicio de sesion para los usuarios de las tiendas
    
    cur.execute("SELECT * FROM usuarios_tiendas WHERE email = %s AND contraseña = %s", (email, contraseña))
    user = cur.fetchone()

    if user is not None:
        session['idTiendas'] = user[0]
        session['email'] = email
        session['name'] = user[1]
        session['surname'] = user[2]
        session['tienda'] = user[3]
        session['contraseña'] = user[5]
        cur.close()
        return redirect(url_for('tiendasUI'))
    else:
        return render_template('index.html', message="Las credenciales no son correctas")
    



# Template de registro de usuarios
@app.route("/regist", methods=['GET'])
def regist():
    return render_template('regist.html')



# Creacion de usuarios
@app.route("/user_regist", methods=['POST'])
def userRegist():
    name = request.form['name']
    surname = request.form['surname']
    tienda = request.form['tienda']
    email = request.form['email']
    contraseña = request.form['contraseña']
    tipo = request.form['tipo-usuario']
    cont_hash = generate_password_hash(contraseña, method='scrypt')

    try:
      if tipo == 'tienda':
        sql = "INSERT INTO usuarios_tiendas (name, surname, tienda, email, contraseña) VALUES (%s, %s, %s, %s, %s)"
        data = (name, surname, tienda, email, cont_hash)
      elif tipo == 'sambil':
        sql = "INSERT INTO login (name, surname, email, contraseña) VALUES (%s, %s, %s, %s)"
        data = (name, surname, email, cont_hash)
      else:
        return redirect(url_for('regist', message='Debe escoger el tipo de usuario'))

      cur = mysql.connection.cursor()
      cur.execute(sql, data)
      mysql.connection.commit()
      cur.close()  # Cerrar el cursor después de ejecutar la consulta

      return render_template('index.html')

    except pymysql.Error as e:
      messageSql = 'Error SQL: {}'.format(str(e))
      return messageSql
    



# Template del inbox para el departamento de fallas 
@app.route("/inbox", methods=['GET'])
def inbox():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM odt")
    fallas = cur.fetchall()
    insertObject = []
    columNamnes = [column[0] for column in cur.description]
    for record in fallas:
          insertObject.append(dict(zip(columNamnes, record)))
    cur.close()
    return render_template('inbox.html', fallas = insertObject)

@app.route("/date", methods=['GET'])
def date():
    return render_template('date.html')




# Funcion para buscar una falla filtrando por fecha
@app.route("/date-filter", methods=['POST'])
def dateFilter():
    fecha1 = request.form['fecha-1']
    fecha2 = request.form['fecha-2']
    if fecha1 and fecha2:
        cur = mysql.connection.cursor()
        sql = "SELECT * FROM odt WHERE fecha BETWEEN %s AND %s"
        data = (fecha1, fecha2)
        cur.execute(sql, data)
        fallas = cur.fetchall()
        insertObject = []
        columNamnes = [column[0] for column in cur.description]
        for record in fallas:
            insertObject.append(dict(zip(columNamnes, record)))
        cur.close()
        return render_template('date.html', fallas=insertObject)
    else:
        # En caso de que no se proporcionen fechas, puedes mostrar todas las fallas
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM odt")
        fallas = cur.fetchall()
        insertObject = []
        columNamnes = [column[0] for column in cur.description]
        for record in fallas:
            insertObject.append(dict(zip(columNamnes, record)))
        cur.close()
        return render_template('inbox.html', fallas=insertObject)




# Funcion para editar las fallas almacenadas 

@app.route("/edit-falla", methods=['POST'])
def editFalla():
    tienda = request.form['tienda']
    name = request.form['name']
    surname = request.form['surname']
    area = request.form['area']
    tipo = request.form['tipo']
    descripcion = request.form['descripcion']
    fecha = request.form['fecha']
    idFalla = request.form['id']

    if name and surname and tienda and area and tipo and descripcion and fecha:
        cur = mysql.connection.cursor()
        sql = 'UPDATE odt SET name = %s, surname = %s, tienda = %s, area = %s, tipo = %s, descripcion = %s, fecha = %s WHERE id = %s'
        data = (name, surname, tienda, area, tipo, descripcion, fecha, idFalla)
        cur.execute(sql, data)
        mysql.connection.commit()
        cur.close()
    return redirect(url_for('inbox'))



# Template para la gestion de usuarios del sambil

@app.route("/editUser", methods=['GET'])
def editUser():
    return render_template('editUser.html')


# Funcion para editar usuarios del sambil
@app.route("/edit-user", methods = ['POST'])
def editUsers():
    ID = session['id']
    name = request.form['name']
    surname = request.form['surname']
    email = request.form['email']
    contAct = request.form['contraseña_Act']
    cont = request.form['contraseña']

    if name and surname and email and cont and contAct == session['contraseña']:
        cur = mysql.connection.cursor()
        sql = "UPDATE login SET name = %s, surname = %s, email = %s, contraseña = %s WHERE id = %s"
        data = (name, surname, email, cont, ID)
        cur.execute(sql, data)
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('home'))
    elif name and surname and email:
        cur = mysql.connection.cursor()
        sql = "UPDATE login SET name = %s, surname = %s, email = %s WHERE id = %s"
        data = (name, surname, email, ID)
        cur.execute(sql, data)
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('home'))
    else:
        return redirect(url_for('editUser', message = "Las contrasenas no coinciden"))

# Template para la vista de reportes de fallas

@app.route("/reporte-fallas", methods = ['GET'])
def reporteFallas():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM odt")
    fallas = cur.fetchall()
    insertObject = []
    columNamnes = [column[0] for column in cur.description]
    for record in fallas:
          insertObject.append(dict(zip(columNamnes, record)))
    cur.close()
    return render_template('reporteFallas.html', fallas = insertObject)

# Template para la vista de reportes de tiendas registradas

@app.route("/reporte-tiendas", methods = ['GET'])
def reporteTiendas():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM usuarios_tiendas")
    tiendas = cur.fetchall()
    insertObject = []
    columNamnes = [column[0] for column in cur.description]
    for record in tiendas:
          insertObject.append(dict(zip(columNamnes, record)))
    cur.close()

    return render_template("reporteTiendas.html", tiendas = insertObject)



# Template para las tiendas
@app.route("/tiendasUI", methods=['GET'])
def tiendasUI():
    email = session['email']
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM odt WHERE email = %s", [email])
    fallas = cur.fetchall()

    insertObject = []
    columNamnes = [column[0] for column in cur.description]
    for record in fallas:
        insertObject.append(dict(zip(columNamnes, record)))
    cur.close()
    return render_template('tiendasUI.html', fallas = insertObject)



# Agregar nueva falla
@app.route("/new-falla", methods=['POST'])
def newFalla():
    email = session['email']
    tienda = session['tienda']
    name = session['name']
    surname = session['surname']
    area = request.form['area']
    tipo = request.form['tipo']
    descripcion = request.form['descripcion']
    fecha = request.form['fecha']

    if tienda and area and tipo and descripcion and fecha:
        cur = mysql.connection.cursor()
        sql = "INSERT INTO odt (email, name, surname, tienda, area, tipo, descripcion, fecha) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        data = (email, name, surname, tienda, area, tipo, descripcion, fecha)
        cur.execute(sql, data)
        mysql.connection.commit()
    return redirect(url_for('tiendasUI'))



# Template para la gestiion de usuarios de las tiendas
@app.route("/editUserTiendas", methods=['GET'])
def editUserTiendas():
    return render_template('editUserTiendas.html')


# Funcion para editar usuarios de las tiendas
@app.route("/edit-user-tiendas", methods = ['POST'])
def editUsersTiendasFunc():
    idTiendas = request.form['id']
    name = request.form['name']
    surname = request.form['surname']
    tienda = request.form['tienda']
    email = request.form['email']
    cont_act = request.form['contraseña_Act']           
    cont = request.form['contraseña']

    
    if name and surname and tienda and email:
      if cont_act == session['contraseña']:
         cur = mysql.connection.cursor()
         sql = "UPDATE usuarios_tiendas SET name = %s, surname = %s, tienda = %s, email = %s, contraseña = %s WHERE idTiendas = %s"
         data = (name, surname, tienda, email, cont, idTiendas)
         cur.execute(sql, data)
         mysql.connection.commit()
         cur.close()
         return redirect(url_for('home'))
      else:
         return redirect(url_for('editUserTiendas'), message='Contraseña incorrecta')
    else:
        return redirect(url_for('editUserTiendas'), message='Los campos Nombre, apellido y Email no deben estar vacíos')

# Eliminar falla
@app.route("/delete-falla", methods=['POST'])
def deleteFalla():
    cur = mysql.connection.cursor()
    id = request.form['id']
    sql = "DELETE FROM odt WHERE id = %s"
    data = (id,)
    cur.execute(sql, data)
    mysql.connection.commit()
    return redirect(url_for('inbox'))

# Cierre de sesion
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == "__main__":
   app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
