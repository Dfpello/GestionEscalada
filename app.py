import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta

# 1. Configuración de la interfaz
st.set_page_config(page_title="Portal de Escalada", page_icon="🧗‍♂️", layout="wide")

# --- SISTEMA DE SEGURIDAD (CONTRASEÑA) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.warning("Portal privado. Por favor, identifícate.")
        pwd = st.text_input("Contraseña", type="password")
        if pwd:
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        st.stop() # Detiene la ejecución si no hay login correcto

check_password()
# -----------------------------------------

GRADOS_ORDEN = {
    "5a": 1, "5b": 2, "5c": 3,
    "6a": 4, "6a+": 5, "6b": 6, "6b+": 7, "6c": 8, "6c+": 9,
    "7a": 10, "7a+": 11, "7b": 12, "7b+": 13, "7c": 14, "7c+": 15
}

ROCODROMOS = [
    "Sputnik Las Rozas",
    "Sputnik Legazpi",
    "Sputnik Chamberí",
    "Sputnik Alcobendas",
    "Sputnik Asturias"
]

DIAS_SEMANA_ES = {
    0: "1. Lunes", 1: "2. Martes", 2: "3. Miércoles",
    3: "4. Jueves", 4: "5. Viernes", 5: "6. Sábado", 6: "7. Domingo"
}

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

# 2. Conexión a Google Sheets (Modificada para usar st.secrets)
@st.cache_resource
def conectar_workbook():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Cargamos las credenciales desde los secretos en lugar de un archivo local
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("Registro de Escalada")

try:
    wb = conectar_workbook()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# 3. Optimización técnica: Caché en la lectura de datos
@st.cache_data(ttl=3600)
def cargar_dataframe(nombre_pestaña):
    try:
        ws = wb.worksheet(nombre_pestaña)
        values = ws.get_all_values()
        if len(values) <= 1:
            return pd.DataFrame()
        headers = [h.strip().capitalize() for h in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)
        df = df.loc[:, df.columns != ""]
        
        # Procesamiento genérico de fechas y números
        if "Fecha" in df.columns:
            df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce")
        if "Grado" in df.columns:
            df["Grado_num"] = df["Grado"].map(GRADOS_ORDEN).fillna(0)
        if "Intentos" in df.columns:
            df["Intentos"] = pd.to_numeric(df["Intentos"], errors="coerce").fillna(1)
            
        # Forzar tipos numéricos para la tabla Físico
        cols_num = ["Peso", "Cintura", "Cuello", "Hombros", "Brazo", "Gemelo", "Imc"]
        for c in cols_num:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
                
        return df
    except Exception as err:
        st.error(f"Error cargando {nombre_pestaña}: {err}")
        return pd.DataFrame()

def calcular_metros_totales(df_vias):
    if df_vias.empty or "Muro" not in df_vias.columns:
        return 0.0
    
    def m_row(r):
        base = 15.0 if r.get("Muro") == "15m" else (20.0 if r.get("Muro") == "20m" else 0.0)
        if str(r.get("Estilo")).lower() == "fallada":
            return base / 2.0
        return base
        
    return float(df_vias.apply(m_row, axis=1).sum())

# --- MENÚ LATERAL DE NAVEGACIÓN WEB ---
st.sidebar.title("🧗‍♂️ Menú Principal")
disciplina = st.sidebar.radio("Selecciona el área:", ["🧗‍♀️ Vía", "🧱 Boulder", "⚖️ Composición Corporal"])

st.sidebar.divider()
st.sidebar.info("Navega entre las disciplinas de escalada o accede al registro de tu evolución física.")

# --- LÓGICA: ESCALADA (VÍA / BOULDER) ---
if disciplina in ["🧗‍♀️ Vía", "🧱 Boulder"]:
    
    if disciplina == "🧗‍♀️ Vía":
        sheet_name = "Vía"
        muro_opciones = ["15m", "20m"]
        icono_seccion = "🧗‍♀️"
    else:
        sheet_name = "Boulder"
        muro_opciones = ["Zona Boulder", "Plafón", "Cueva"]
        icono_seccion = "🧱"

    df_data = cargar_dataframe(sheet_name)

    st.title(f"{icono_seccion} Sección de {sheet_name}")

    tab_reg, tab_week, tab_month, tab_history, tab_search = st.tabs([
        "📝 Registrar", 
        "📊 Esta Semana", 
        "📅 Este Mes", 
        "📈 Histórico", 
        "🔍 Buscador"
    ])

    # 1. REGISTRAR ESCALADA
    with tab_reg:
        st.subheader(f"Añadir nuevo registro de {sheet_name}")
        
        with st.form("form_registro", clear_on_submit=True):
            fecha = st.date_input("Fecha", datetime.today())
            rocodromo = st.selectbox("Rocódromo", ROCODROMOS)
            muro = st.selectbox("Muro / Zona", muro_opciones)
            grado = st.selectbox("Grado", list(GRADOS_ORDEN.keys()), index=6) 
            estilo = st.selectbox("Estilo", ["Flash", "Fallada", "Repetida", "Proceso"])
            intentos = st.number_input("Intentos", min_value=1, value=1, step=1)
            notas = st.text_area("Notas / Sensaciones")
            
            submit = st.form_submit_button(f"Guardar en {sheet_name} 🚀")
            
            if submit:
                try:
                    ws_sheet = wb.worksheet(sheet_name)
                    ws_sheet.append_row(
                        [str(fecha), rocodromo, muro, grado, estilo, int(intentos), notas],
                        value_input_option='USER_ENTERED'
                    )
                    st.success(f"¡Guardado correctamente en {sheet_name}! ({grado} en {muro} - {rocodromo})")
                    st.cache_data.clear() # Limpia la caché para obligar a refrescar la lectura
                except Exception as err:
                    st.error(f"Error al guardar: {err}")

    if not df_data.empty and "Fecha_dt" in df_data.columns:
        df_valid = df_data.dropna(subset=["Fecha_dt"]).sort_values("Fecha_dt", ascending=False)
    else:
        df_valid = pd.DataFrame()

    # 2. ESTADÍSTICAS DE ESTA SEMANA
    with tab_week:
        st.subheader(f"📊 Actividad de {sheet_name} (Semana Actual)")
        
        if df_valid.empty:
            st.info(f"Aún no hay registros cargados en {sheet_name}.")
        else:
            hoy = datetime.today().date()
            lunes_actual = hoy - timedelta(days=hoy.weekday())
            domingo_actual = lunes_actual + timedelta(days=6)
            
            st.caption(f"Semana del **{lunes_actual.strftime('%d/%m/%Y')}** al **{domingo_actual.strftime('%d/%m/%Y')}**")
            
            df_sem = df_valid[
                (df_valid["Fecha_dt"].dt.date >= lunes_actual) & 
                (df_valid["Fecha_dt"].dt.date <= domingo_actual)
            ].copy()
            
            if df_sem.empty:
                st.info(f"No has registrado ninguna sesión de {sheet_name} esta semana.")
            else:
                df_sem["Dia_Semana"] = df_sem["Fecha_dt"].dt.weekday.map(DIAS_SEMANA_ES)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Días Entrenados", df_sem["Fecha_dt"].nunique())
                c2.metric("Total Pegues", len(df_sem))
                
                if "Estilo" in df_sem.columns:
                    exitosos = len(df_sem[df_sem["Estilo"].isin(["Flash", "Repetida"])])
                    tasa_exito = round((exitosos / len(df_sem)) * 100, 1)
                    c3.metric("Efectividad", f"{tasa_exito}%")
                    
                if sheet_name == "Vía":
                    total_m = calcular_metros_totales(df_sem)
                    c4.metric("Metros Vía", f"{total_m:g} m")
                elif "Grado_num" in df_sem.columns:
                    df_exitosas_sem = df_sem[df_sem["Estilo"].str.lower() != "fallada"]
                    if not df_exitosas_sem.empty:
                        max_sem = df_exitosas_sem.sort_values("Grado_num", ascending=False).iloc[0]
                        c4.metric("Top Grado", max_sem["Grado"], max_sem.get("Estilo", ""))
                    else:
                        c4.metric("Top Grado", "N/A")

                st.divider()
                cg1, cg2 = st.columns(2)
                with cg1:
                    st.markdown(f"##### Pegues por día")
                    st.bar_chart(df_sem.groupby("Dia_Semana").size())
                with cg2:
                    st.markdown(f"##### Pirámide de Grados")
                    if "Grado" in df_sem.columns:
                        df_sem_sorted = df_sem.sort_values("Grado_num")
                        st.bar_chart(df_sem_sorted["Grado"].value_counts()[df_sem_sorted["Grado"].unique()])
                        
                st.divider()
                cols_v = [c for c in ["Fecha", "Rocódromo", "Muro", "Grado", "Estilo", "Intentos", "Notas"] if c in df_sem.columns]
                st.data_editor(df_sem[cols_v], use_container_width=True, hide_index=True, key="editor_semana")

    # 3. ESTADÍSTICAS DEL MES
    with tab_month:
        st.subheader(f"📅 Estadísticas Mensuales ({sheet_name})")
        if not df_valid.empty:
            df_m = df_valid.copy()
            df_m["Año"] = df_m["Fecha_dt"].dt.year
            df_m["Mes_Num"] = df_m["Fecha_dt"].dt.month
            df_m["Mes_Nombre"] = df_m["Mes_Num"].map(MESES_ES)
            df_m["Mes_Label"] = df_m["Año"].astype(str) + " - " + df_m["Mes_Nombre"]
            
            meses_opciones = df_m["Mes_Label"].unique()
            mes_seleccionado = st.selectbox("Selecciona un mes para consultar:", meses_opciones, key="month_select")
            
            df_mes = df_m[df_m["Mes_Label"] == mes_seleccionado].copy()
            
            if not df_mes.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Días Escalados", df_mes["Fecha_dt"].nunique())
                c2.metric("Total Pegues", len(df_mes))
                
                if "Estilo" in df_mes.columns:
                    exitosos = len(df_mes[df_mes["Estilo"].isin(["Flash", "Repetida"])])
                    tasa_exito = round((exitosos / len(df_mes)) * 100, 1)
                    c3.metric("Efectividad", f"{tasa_exito}%")
                    
                if sheet_name == "Vía":
                    total_m_mes = calcular_metros_totales(df_mes)
                    c4.metric("Metros Vía", f"{total_m_mes:g} m")
                elif "Grado_num" in df_mes.columns:
                    df_exitosas_m = df_mes[df_mes["Estilo"].str.lower() != "fallada"]
                    if not df_exitosas_m.empty:
                        max_m = df_exitosas_m.sort_values("Grado_num", ascending=False).iloc[0]
                        c4.metric("Top Grado Mes", max_m["Grado"], max_m.get("Estilo", ""))
                    else:
                        c4.metric("Top Grado Mes", "N/A")
                    
                st.divider()
                cm1, cm2 = st.columns(2)
                with cm1:
                    st.markdown("##### Pegues por Día del Mes")
                    df_mes["Día_Str"] = df_mes["Fecha_dt"].dt.strftime('%d/%m')
                    st.bar_chart(df_mes.groupby("Día_Str").size())
                with cm2:
                    st.markdown("##### Pirámide de Grados del Mes")
                    if "Grado" in df_mes.columns:
                        df_mes_sorted = df_mes.sort_values("Grado_num")
                        st.bar_chart(df_mes_sorted["Grado"].value_counts()[df_mes_sorted["Grado"].unique()])
                        
                st.divider()
                cols_m = [c for c in ["Fecha", "Rocódromo", "Muro", "Grado", "Estilo", "Intentos", "Notas"] if c in df_mes.columns]
                st.data_editor(df_mes[cols_m], use_container_width=True, hide_index=True, key="editor_mes")

    # 4. HISTÓRICO GLOBAL
    with tab_history:
        st.subheader(f"📈 Progresión Histórica de {sheet_name}")
        if not df_valid.empty:
            df_hist = df_valid.sort_values("Fecha_dt")
            df_hist["Semana_Hist"] = df_hist["Fecha_dt"].dt.strftime('%Y-W%U')
            
            st.markdown("##### Evolución de volumen semana a semana")
            st.bar_chart(df_hist.groupby("Semana_Hist").size())
            
            c1, c2, c3 = st.columns(3)
            semanas_tot = df_hist["Semana_Hist"].nunique()
            tot_acum = len(df_hist)
            c1.metric("Semanas Activas", semanas_tot)
            c2.metric("Total Pegues", tot_acum)
            c3.metric("Promedio Semanal", f"{round(tot_acum / max(1, semanas_tot), 1)} /sem")
            
            st.divider()
            if "Grado_num" in df_hist.columns:
                df_exitosas_h = df_hist[df_hist["Estilo"].str.lower() != "fallada"]
                if not df_exitosas_h.empty:
                    top_h = df_exitosas_h.sort_values("Grado_num", ascending=False).iloc[0]
                    st.metric(f"🏆 Récord Máximo Histórico ({sheet_name})", top_h["Grado"], f"{top_h.get('Muro', '')} ({top_h.get('Estilo', '')})")

    # 5. BUSCADOR POR FECHA
    with tab_search:
        st.subheader(f"🔍 Buscador de {sheet_name}")
        if not df_valid.empty:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                hoy = datetime.today().date()
                hace_un_mes = hoy - timedelta(days=30)
                rango_fechas = st.date_input("Rango de Fechas", value=(hace_un_mes, hoy), key="search_range")
            with col_f2:
                grados_disponibles = ["Todos"] + list(df_valid["Grado"].unique()) if "Grado" in df_valid.columns else ["Todos"]
                filtro_grado = st.selectbox("Filtrar por Grado", grados_disponibles, key="search_grade")
                
            df_filt = df_valid.copy()
            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                f_ini, f_fin = rango_fechas
                df_filt = df_filt[
                    (df_filt["Fecha_dt"].dt.date >= f_ini) & 
                    (df_filt["Fecha_dt"].dt.date <= f_fin)
                ]
                
            if filtro_grado != "Todos" and "Grado" in df_filt.columns:
                df_filt = df_filt[df_filt["Grado"] == filtro_grado]
                
            st.markdown(f"**Resultados encontrados:** `{len(df_filt)}`")
            if not df_filt.empty:
                cols_s = [c for c in ["Fecha", "Rocódromo", "Muro", "Grado", "Estilo", "Intentos", "Notas"] if c in df_filt.columns]
                st.data_editor(df_filt[cols_s], use_container_width=True, hide_index=True, key="editor_buscador")


# --- LÓGICA: COMPOSICIÓN CORPORAL ---
elif disciplina == "⚖️ Composición Corporal":
    sheet_name_fisico = "Físico"
    df_fisico = cargar_dataframe(sheet_name_fisico)

    st.title("⚖️ Evolución Física y Recomposición")
    
    tab_reg_fisico, tab_graficas = st.tabs(["📝 Registrar Medidas", "📉 Evolución y Tracking"])
    
    # 1. REGISTRAR MEDIDAS
    with tab_reg_fisico:
        st.subheader("Añadir nuevo registro de composición")
        st.info("Asegúrate de tomar las medidas siempre en las mismas condiciones (p. ej. por la mañana en ayunas).")
        
        with st.form("form_fisico", clear_on_submit=True):
            fecha_fisico = st.date_input("Fecha", datetime.today())
            
            # Altura fija para el cálculo automatizado del IMC
            altura_m = 1.73
            st.caption(f"📏 *Altura de referencia configurada: {altura_m} m*")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                peso = st.number_input("Peso (kg)", min_value=50.0, max_value=120.0, value=75.2, step=0.1)
                cintura = st.number_input("Cintura (cm)", min_value=50.0, value=80.0, step=0.5)
                cuello = st.number_input("Cuello (cm)", min_value=20.0, value=38.0, step=0.5)
            with col_f2:
                hombros = st.number_input("Hombros (cm)", min_value=80.0, value=115.0, step=0.5)
                brazo = st.number_input("Brazo (cm)", min_value=20.0, value=33.0, step=0.5)
                gemelo = st.number_input("Gemelo (cm)", min_value=20.0, value=38.0, step=0.5)
            
            submit_fisico = st.form_submit_button("Guardar medidas 🚀")
            
            if submit_fisico:
                imc = round(peso / (altura_m ** 2), 2)
                try:
                    ws_fisico = wb.worksheet(sheet_name_fisico)
                    # Comprueba si la hoja está vacía para escribir las cabeceras la primera vez
                    if len(ws_fisico.get_all_values()) == 0:
                        ws_fisico.append_row(["Fecha", "Peso", "Cintura", "Cuello", "Hombros", "Brazo", "Gemelo", "Imc"])
                    
                    ws_fisico.append_row(
                        [str(fecha_fisico), peso, cintura, cuello, hombros, brazo, gemelo, imc],
                        value_input_option='USER_ENTERED'
                    )
                    st.success("¡Medidas guardadas correctamente!")
                    st.cache_data.clear()
                except Exception as err:
                    st.error(f"Error al guardar medidas. Asegúrate de tener una pestaña llamada 'Físico' creada en tu Google Sheet: {err}")

    # 2. GRÁFICAS DE EVOLUCIÓN
    with tab_graficas:
        st.subheader("Progresión a lo largo del tiempo")
        
        if df_fisico.empty or "Fecha_dt" not in df_fisico.columns:
            st.warning("No hay suficientes registros. Añade tu primera entrada de medidas.")
        else:
            df_f_valid = df_fisico.dropna(subset=["Fecha_dt"]).sort_values("Fecha_dt")
            df_f_valid.set_index("Fecha_dt", inplace=True)
            
            # Bloque de KPIs
            if not df_f_valid.empty:
                ultimos_datos = df_f_valid.iloc[-1]
                c1, c2, c3 = st.columns(3)
                
                peso_actual = ultimos_datos.get("Peso", 0)
                imc_actual = ultimos_datos.get("Imc", round(peso_actual / (1.73**2), 2))
                
                if len(df_f_valid) > 1:
                    peso_anterior = df_f_valid.iloc[-2].get("Peso", peso_actual)
                    diff_peso = round(peso_actual - peso_anterior, 1)
                    c1.metric("Último Peso", f"{peso_actual} kg", f"{diff_peso} kg", delta_color="inverse")
                else:
                    c1.metric("Último Peso", f"{peso_actual} kg")
                    
                c2.metric("IMC Actual", f"{imc_actual}")
                c3.metric("Último Gemelo", f"{ultimos_datos.get('Gemelo', 0)} cm")
            
            st.divider()
            
            st.markdown("##### 📉 Fluctuación de Peso (kg)")
            if "Peso" in df_f_valid.columns:
                st.line_chart(df_f_valid["Peso"], color="#FF4B4B")
                
            st.markdown("##### 📏 Evolución Perimetral (cm)")
            cols_graf = [c for c in ["Cintura", "Hombros", "Gemelo", "Brazo", "Cuello"] if c in df_f_valid.columns]
            if cols_graf:
                st.line_chart(df_f_valid[cols_graf])
                
            st.divider()
            st.markdown("##### Registro Histórico")
            st.info("Los datos se muestran a través de `st.data_editor` y permiten manipulación directa desde la interfaz antes de exportarlos o analizarlos.")
            st.data_editor(df_fisico.drop(columns=["Fecha_dt"], errors="ignore"), use_container_width=True, hide_index=True, key="editor_fisico")