import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "8525210382:AAEZBdMNegcpFiC8hjLmM0gboHqt3b94OY0")

# Estados del ConversationHandler
(NOMBRE, EDAD, GENERO, BUSCA, PAIS, BIO, FOTO, MENU_PRINCIPAL, ESCRIBIR_MENSAJE) = range(9)

# â”€â”€â”€ BASE DE DATOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def init_db():
    conn = sqlite3.connect("conectabot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            nombre      TEXT,
            edad        INTEGER,
            genero      TEXT,
            busca       TEXT,
            pais        TEXT,
            bio         TEXT,
            foto_id     TEXT,
            activo      INTEGER DEFAULT 1,
            creado_en   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            de_user   INTEGER,
            a_user    INTEGER,
            PRIMARY KEY (de_user, a_user)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            user1     INTEGER,
            user2     INTEGER,
            PRIMARY KEY (user1, user2)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS vistos (
            de_user   INTEGER,
            a_user    INTEGER,
            PRIMARY KEY (de_user, a_user)
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect("conectabot.db")

def guardar_usuario(user_id, username, nombre, edad, genero, busca, pais, bio, foto_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO usuarios
        (user_id, username, nombre, edad, genero, busca, pais, bio, foto_id, activo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (user_id, username, nombre, edad, genero, busca, pais, bio, foto_id))
    conn.commit()
    conn.close()

def obtener_usuario(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def obtener_candidatos(user_id, busca_genero):
    conn = get_db()
    c = conn.cursor()
    # Excluir ya vistos, el propio usuario, inactivos
    c.execute("""
        SELECT user_id, nombre, edad, genero, pais, bio, foto_id
        FROM usuarios
        WHERE user_id != ?
          AND activo = 1
          AND (? = 'Todos' OR genero = ?)
          AND user_id NOT IN (
              SELECT a_user FROM vistos WHERE de_user = ?
          )
        ORDER BY RANDOM()
        LIMIT 1
    """, (user_id, busca_genero, busca_genero, user_id))
    row = c.fetchone()
    conn.close()
    return row

def registrar_visto(de_user, a_user):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO vistos (de_user, a_user) VALUES (?, ?)", (de_user, a_user))
    conn.commit()
    conn.close()

def registrar_like(de_user, a_user):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO likes (de_user, a_user) VALUES (?, ?)", (de_user, a_user))
    conn.commit()
    # Â¿Match mutuo?
    c.execute("SELECT 1 FROM likes WHERE de_user = ? AND a_user = ?", (a_user, de_user))
    es_match = c.fetchone() is not None
    if es_match:
        u1, u2 = min(de_user, a_user), max(de_user, a_user)
        c.execute("INSERT OR IGNORE INTO matches (user1, user2) VALUES (?, ?)", (u1, u2))
        conn.commit()
    conn.close()
    return es_match

# â”€â”€â”€ HELPERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def perfil_texto(nombre, edad, genero, pais, bio):
    emoji_genero = "ðŸ‘¨" if genero == "Hombre" else "ðŸ‘©" if genero == "Mujer" else "ðŸ§‘"
    return (
        f"{emoji_genero} *{nombre}*, {edad} aÃ±os\n"
        f"ðŸŒ {pais}\n"
        f"ðŸ“ {bio}"
    )

def teclado_explorar():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("â¤ï¸ Me gusta", callback_data="like"),
            InlineKeyboardButton("ðŸ‘Ž Siguiente", callback_data="skip"),
        ],
        [
            InlineKeyboardButton("ðŸ’¬ Enviar mensaje", callback_data="mensaje"),
        ],
        [
            InlineKeyboardButton("â­ Mi perfil", callback_data="mi_perfil"),
            InlineKeyboardButton("âœï¸ Editar", callback_data="editar"),
        ]
    ])

# â”€â”€â”€ REGISTRO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    usuario = obtener_usuario(user_id)
    if usuario:
        await update.message.reply_text(
            f"ðŸ‘‹ Â¡Bienvenido de vuelta, *{usuario[2]}*!\n\nUsa /explorar para conocer gente o /perfil para ver tu perfil.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "ðŸŒŸ *Â¡Bienvenido a ConectaBot!*\n\n"
        "AquÃ­ puedes conocer personas de todo el mundo â€” amistad o pareja, tÃº decides.\n\n"
        "Vamos a crear tu perfil. Es rÃ¡pido âš¡\n\n"
        "Â¿CuÃ¡l es tu *nombre* (o como quieres que te llamen)?",
        parse_mode="Markdown"
    )
    return NOMBRE

async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    if len(nombre) < 2 or len(nombre) > 30:
        await update.message.reply_text("El nombre debe tener entre 2 y 30 caracteres. Intenta de nuevo:")
        return NOMBRE
    context.user_data["nombre"] = nombre
    await update.message.reply_text(f"Perfecto, *{nombre}* ðŸ˜Š\n\nÂ¿CuÃ¡ntos aÃ±os tienes?", parse_mode="Markdown")
    return EDAD

async def recibir_edad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        edad = int(update.message.text.strip())
        if edad < 18 or edad > 99:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Ingresa una edad vÃ¡lida (18-99):")
        return EDAD
    context.user_data["edad"] = edad

    teclado = ReplyKeyboardMarkup(
        [["Hombre", "Mujer", "Otro"]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text("Â¿CuÃ¡l es tu gÃ©nero?", reply_markup=teclado)
    return GENERO

async def recibir_genero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    genero = update.message.text.strip()
    if genero not in ["Hombre", "Mujer", "Otro"]:
        await update.message.reply_text("Elige una opciÃ³n: Hombre, Mujer u Otro")
        return GENERO
    context.user_data["genero"] = genero

    teclado = ReplyKeyboardMarkup(
        [["Hombres", "Mujeres", "Todos"]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text("Â¿A quiÃ©n quieres conocer?", reply_markup=teclado)
    return BUSCA

async def recibir_busca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    busca = update.message.text.strip()
    opciones = {"Hombres": "Hombre", "Mujeres": "Mujer", "Todos": "Todos"}
    if busca not in opciones:
        await update.message.reply_text("Elige: Hombres, Mujeres o Todos")
        return BUSCA
    context.user_data["busca"] = opciones[busca]
    await update.message.reply_text(
        "ðŸŒ Â¿De quÃ© paÃ­s eres? (Escribe el nombre, ej: RepÃºblica Dominicana, MÃ©xico, EspaÃ±a...)"
    )
    return PAIS

async def recibir_pais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pais = update.message.text.strip()
    if len(pais) < 2 or len(pais) > 50:
        await update.message.reply_text("Nombre de paÃ­s invÃ¡lido. Intenta de nuevo:")
        return PAIS
    context.user_data["pais"] = pais
    await update.message.reply_text(
        "âœï¸ Escribe una *bio* corta sobre ti â€” quÃ© te gusta, quÃ© buscas, algo que te describa.\n"
        "_(MÃ¡x. 200 caracteres)_",
        parse_mode="Markdown"
    )
    return BIO

async def recibir_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text.strip()
    if len(bio) > 200:
        await update.message.reply_text("Muy larga. MÃ¡ximo 200 caracteres:")
        return BIO
    context.user_data["bio"] = bio
    await update.message.reply_text(
        "ðŸ“¸ Ahora envÃ­a una *foto* tuya para tu perfil.",
        parse_mode="Markdown"
    )
    return FOTO

async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Por favor envÃ­a una foto:")
        return FOTO

    foto_id = update.message.photo[-1].file_id
    user = update.effective_user
    datos = context.user_data

    guardar_usuario(
        user.id, user.username,
        datos["nombre"], datos["edad"], datos["genero"],
        datos["busca"], datos["pais"], datos["bio"], foto_id
    )

    await update.message.reply_text(
        f"ðŸŽ‰ *Â¡Perfil creado!*\n\n"
        f"{perfil_texto(datos['nombre'], datos['edad'], datos['genero'], datos['pais'], datos['bio'])}\n\n"
        f"Usa /explorar para empezar a conocer gente ðŸš€",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# â”€â”€â”€ EXPLORAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def explorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    usuario = obtener_usuario(user_id)
    if not usuario:
        await update.message.reply_text("Primero crea tu perfil con /start")
        return

    busca = usuario[4]  # campo busca
    candidato = obtener_candidatos(user_id, busca)

    if not candidato:
        await update.message.reply_text(
            "ðŸ˜… No hay mÃ¡s perfiles disponibles por ahora.\n"
            "Vuelve mÃ¡s tarde cuando se unan mÃ¡s personas."
        )
        return

    cand_id, nombre, edad, genero, pais, bio, foto_id = candidato
    context.user_data["candidato_actual"] = cand_id

    caption = perfil_texto(nombre, edad, genero, pais, bio)
    await update.message.bot.send_photo(
        chat_id=user_id,
        photo=foto_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=teclado_explorar()
    )

async def callback_explorar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    accion = query.data

    if accion == "mi_perfil":
        await mostrar_mi_perfil(update, context)
        return

    if accion == "editar":
        await query.message.reply_text("Para editar tu perfil usa /editar")
        return

    if accion == "mensaje":
        candidato_id = context.user_data.get("candidato_actual")
        if not candidato_id:
            await query.message.reply_text("Usa /explorar para ver perfiles.")
            return
        su_info = obtener_usuario(candidato_id)
        context.user_data["mensaje_para"] = candidato_id
        context.user_data["mensaje_para_nombre"] = su_info[2] if su_info else "esa persona"
        await query.message.reply_text(
            f"ðŸ’¬ Escribe tu mensaje para *{context.user_data['mensaje_para_nombre']}*\n"
            f"_(MÃ¡x. 300 caracteres. Escribe /cancelar para volver)_",
            parse_mode="Markdown"
        )
        context.user_data["esperando_mensaje"] = True
        return

    candidato_id = context.user_data.get("candidato_actual")
    if not candidato_id:
        await query.message.reply_text("Usa /explorar para ver perfiles.")
        return

    registrar_visto(user_id, candidato_id)

    if accion == "like":
        es_match = registrar_like(user_id, candidato_id)
        if es_match:
            # Obtener info de ambos para notificar
            mi_info = obtener_usuario(user_id)
            su_info = obtener_usuario(candidato_id)
            mi_username = f"@{query.from_user.username}" if query.from_user.username else mi_info[2]
            su_username = f"@{su_info[1]}" if su_info[1] else su_info[2]

            # Notificar a ambos
            await query.message.reply_text(
                f"ðŸŽ‰ *Â¡Es un Match!*\n\nA *{su_info[2]}* tambiÃ©n le gustaste.\n"
                f"Puedes escribirle: {su_username}",
                parse_mode="Markdown"
            )
            try:
                await query.bot.send_message(
                    chat_id=candidato_id,
                    text=f"ðŸŽ‰ *Â¡Es un Match!*\n\nA *{mi_info[2]}* le gustaste.\n"
                         f"Puedes escribirle: {mi_username}",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            await query.message.reply_text("â¤ï¸ Â¡Like enviado! Explorando mÃ¡s...")

    # Mostrar siguiente perfil
    usuario = obtener_usuario(user_id)
    busca = usuario[4]
    candidato = obtener_candidatos(user_id, busca)

    if not candidato:
        await query.message.reply_text("No hay mÃ¡s perfiles por ahora. Vuelve mÃ¡s tarde ðŸ˜Š")
        return

    cand_id, nombre, edad, genero, pais, bio, foto_id = candidato
    context.user_data["candidato_actual"] = cand_id

    caption = perfil_texto(nombre, edad, genero, pais, bio)
    await query.message.bot.send_photo(
        chat_id=user_id,
        photo=foto_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=teclado_explorar()
    )

# â”€â”€â”€ PERFIL / EDITAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def mostrar_mi_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        send = update.callback_query.message.reply_text
        send_photo = update.callback_query.message.bot.send_photo
    else:
        user_id = update.effective_user.id
        send = update.message.reply_text
        send_photo = update.message.bot.send_photo

    usuario = obtener_usuario(user_id)
    if not usuario:
        await send("No tienes perfil aÃºn. Usa /start para crearlo.")
        return

    _, username, nombre, edad, genero, busca, pais, bio, foto_id, *_ = usuario
    texto = perfil_texto(nombre, edad, genero, pais, bio)
    texto += f"\n\nðŸ” Buscando: *{busca}*"

    await send_photo(chat_id=user_id, photo=foto_id, caption=texto, parse_mode="Markdown")

async def comando_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mostrar_mi_perfil(update, context)

async def comando_editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Para editar tu perfil, simplemente usa /start de nuevo y te guiarÃ© por el proceso completo.\n"
        "_(Tu perfil anterior serÃ¡ reemplazado)_",
        parse_mode="Markdown"
    )

async def comando_pausa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET activo = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("â¸ï¸ Tu perfil fue pausado. Usa /activar para volver a aparecer.")

async def comando_activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET activo = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("âœ… Tu perfil estÃ¡ activo de nuevo. Â¡A conocer gente!")

async def comando_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ðŸ¤– *ConectaBot â€” Comandos*\n\n"
        "/start â€” Crear o reiniciar perfil\n"
        "/explorar â€” Ver perfiles y dar likes\n"
        "/perfil â€” Ver mi perfil\n"
        "/pausa â€” Ocultar mi perfil temporalmente\n"
        "/activar â€” Volver a aparecer\n"
        "/ayuda â€” Esta ayuda\n\n"
        "â¤ï¸ Cuando dos personas se dan like mutuamente â†’ Â¡Match! y se comparten sus usuarios de Telegram.",
        parse_mode="Markdown"
    )

# â”€â”€â”€ MINI MENSAJE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def recibir_mini_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages when user is in 'escribir mensaje' mode."""
    if not context.user_data.get("esperando_mensaje"):
        return  # not in message mode, ignore

    texto = update.message.text.strip()

    if texto == "/cancelar":
        context.user_data["esperando_mensaje"] = False
        await update.message.reply_text("âŒ Mensaje cancelado. Usa /explorar para seguir viendo perfiles.")
        return

    if len(texto) > 300:
        await update.message.reply_text("Muy largo. MÃ¡ximo 300 caracteres. Intenta de nuevo:")
        return

    destinatario_id = context.user_data.get("mensaje_para")
    destinatario_nombre = context.user_data.get("mensaje_para_nombre", "alguien")
    mi_info = obtener_usuario(update.effective_user.id)
    mi_nombre = mi_info[2] if mi_info else "Alguien"

    # Deliver message to recipient
    try:
        await update.message.bot.send_message(
            chat_id=destinatario_id,
            text=(
                f"ðŸ’Œ *Tienes un mensaje de {mi_nombre}*\n\n"
                f"_{texto}_\n\n"
                f"Si quieres responderle, usa /explorar y bÃºscalo, o escrÃ­bele directamente "
                f"si hacen match."
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"âœ… Â¡Mensaje enviado a *{destinatario_nombre}*!\n\nSiguiendo con mÃ¡s perfiles...",
            parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text(
            "âš ï¸ No se pudo entregar el mensaje (el usuario puede tener el bot bloqueado). "
            "Siguiendo con mÃ¡s perfiles..."
        )

    # Clear state and show next profile
    context.user_data["esperando_mensaje"] = False
    context.user_data.pop("mensaje_para", None)
    context.user_data.pop("mensaje_para_nombre", None)

    # Register as seen (they got a message, no need to show again)
    registrar_visto(update.effective_user.id, destinatario_id)

    # Show next profile
    usuario = obtener_usuario(update.effective_user.id)
    busca = usuario[4]
    candidato = obtener_candidatos(update.effective_user.id, busca)

    if not candidato:
        await update.message.reply_text("No hay mÃ¡s perfiles por ahora. Vuelve mÃ¡s tarde ðŸ˜Š")
        return

    cand_id, nombre, edad, genero, pais, bio, foto_id = candidato
    context.user_data["candidato_actual"] = cand_id
    caption = perfil_texto(nombre, edad, genero, pais, bio)
    await update.message.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=foto_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=teclado_explorar()
    )

# â”€â”€â”€ MAIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NOMBRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre)],
            EDAD:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_edad)],
            GENERO:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_genero)],
            BUSCA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_busca)],
            PAIS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_pais)],
            BIO:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_bio)],
            FOTO:    [MessageHandler(filters.PHOTO, recibir_foto)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("explorar", explorar))
    app.add_handler(CommandHandler("perfil", comando_perfil))
    app.add_handler(CommandHandler("editar", comando_editar))
    app.add_handler(CommandHandler("pausa", comando_pausa))
    app.add_handler(CommandHandler("activar", comando_activar))
    app.add_handler(CommandHandler("ayuda", comando_ayuda))
    # Mini mensaje handler â€” must be BEFORE CallbackQueryHandler to intercept text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_mini_mensaje))
    app.add_handler(CallbackQueryHandler(callback_explorar))

    print("ðŸ¤– ConectaBot corriendo...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
