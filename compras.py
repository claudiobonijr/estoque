import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configurações de Página
st.set_page_config(page_title="Gestão de Estoque Pro", page_icon="🏗️", layout="wide")

# Estilo CSS para melhorar o visual
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Função para ler dados com cache desativado
def carregar_dados(aba):
    try:
        return conn.read(worksheet=aba, ttl=0)
    except:
        return pd.DataFrame()

# Sidebar de Navegação
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/4222/4222961.png", width=100)
st.sidebar.title("Menu de Gestão")
aba_selecionada = st.sidebar.radio("Navegação:", ["📊 Dashboard", "📦 Cadastro & Importação", "📥 Entrada de Material", "📤 Saída/Aplicação", "📜 Histórico Geral"])

# --- LÓGICA DE DADOS ---
df_prod = carregar_dados("produtos")
df_mov = carregar_dados("movimentacoes")

# --- DASHBOARD ---
if aba_selecionada == "📊 Dashboard":
    st.title("📊 Painel de Controle de Estoque")
    
    if not df_mov.empty and "quantidade" in df_mov.columns:
        # Cálculo de Saldo
        df_mov['qtd_ajustada'] = df_mov.apply(lambda x: float(x['quantidade']) if x['tipo'] == 'Entrada' else -float(x['quantidade']), axis=1)
        saldo_df = df_mov.groupby(['codigo', 'descricao']).agg({'qtd_ajustada': 'sum'}).reset_index()
        saldo_df.columns = ['Código', 'Descrição', 'Saldo Atual']

        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Itens Cadastrados", len(df_prod))
        c2.metric("Movimentações Realizadas", len(df_mov))
        c3.metric("Itens com Saldo Baixo", len(saldo_df[saldo_df['Saldo Atual'] < 5]))

        st.markdown("---")
        st.subheader("📦 Inventário em Tempo Real")
        st.dataframe(saldo_df, use_container_width=True, hide_index=True)
        
        if not saldo_df.empty:
            st.bar_chart(data=saldo_df, x='Descrição', y='Saldo Atual')
    else:
        st.info("Aguardando movimentações para gerar o gráfico...")

# --- CADASTRO & IMPORTAÇÃO ---
elif aba_selecionada == "📦 Cadastro & Importação":
    st.title("📦 Gestão de Itens")
    t1, t2 = st.tabs(["Cadastro Manual", "Importar do Mais Controle"])
    
    with t1:
        with st.form("form_manual"):
            col1, col2 = st.columns(2)
            cod = col1.text_input("Código do Insumo")
            desc = col2.text_input("Descrição Completa")
            if st.form_submit_button("Salvar Insumo"):
                if cod and desc:
                    novo = pd.DataFrame([{"codigo": cod, "descricao": desc}])
                    updated = pd.concat([df_prod, novo], ignore_index=True)
                    conn.update(worksheet="produtos", data=updated, spreadsheet=st.secrets["gsheets_url"])
                    st.success("Item cadastrado!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")

    with t2:
        st.subheader("Subir Planilha do Mais Controle")
        arquivo = st.file_uploader("Arraste o Excel/CSV aqui", type=['xlsx', 'csv'])
        if arquivo:
            df_imp = pd.read_excel(arquivo) if arquivo.name.endswith('xlsx') else pd.read_csv(arquivo)
            st.dataframe(df_imp.head(3))
            c_cod = st.selectbox("Coluna do Código:", df_imp.columns)
            c_desc = st.selectbox("Coluna da Descrição:", df_imp.columns)
            if st.button("Confirmar Importação em Massa"):
                mapeado = df_imp[[c_cod, c_desc]].rename(columns={c_cod: 'codigo', c_desc: 'descricao'})
                final = pd.concat([df_prod, mapeado], ignore_index=True).drop_duplicates(subset='codigo')
                conn.update(worksheet="produtos", data=final, spreadsheet=st.secrets["gsheets_url"])
                st.success("Importação concluída com sucesso!")

# --- ENTRADA ---
elif aba_selecionada == "📥 Entrada de Material":
    st.title("📥 Registro de Entrada")
    if df_prod.empty:
        st.error("Cadastre produtos antes de continuar.")
    else:
        with st.form("entrada"):
            col1, col2 = st.columns(2)
            data = col1.date_input("Data da NF/Entrada", datetime.now())
            obra = col1.text_input("Obra Destino")
            lista_p = df_prod['codigo'] + " - " + df_prod['descricao']
            item = col1.selectbox("Selecione o Item", lista_p)
            
            sc = col2.text_input("SC (Solicitação)")
            mapa = col2.text_input("Mapa de Cotação")
            oc = col2.text_input("OC (Ordem de Compra)")
            qtd = col2.number_input("Quantidade Recebida", min_value=0.01)
            
            if st.form_submit_button("Confirmar Recebimento"):
                nova_mov = pd.DataFrame([{
                    "tipo": "Entrada", "data": str(data), "obra": obra, "sc": sc, 
                    "mapa": mapa, "oc": oc, "codigo": item.split(" - ")[0], 
                    "descricao": item.split(" - ")[1], "quantidade": qtd
                }])
                # LINHA CORRIGIDA ABAIXO:
                mov_atualizada = pd.concat([df_mov, nova_mov], ignore_index=True)
                conn.update(worksheet="movimentacoes", data=mov_atualizada, spreadsheet=st.secrets["gsheets_url"])
                st.success("Entrada salva na nuvem!")

# --- SAÍDA ---
elif aba_selecionada == "📤 Saída/Aplicação":
    st.title("📤 Registro de Saída")
    if df_prod.empty:
        st.error("Não há produtos cadastrados para dar saída.")
    else:
        with st.form("saida"):
            col1, col2 = st.columns(2)
            data = col1.date_input("Data da Saída", datetime.now())
            obra = col1.text_input("Obra/Frente de Trabalho")
            lista_p = df_prod['codigo'] + " - " + df_prod['descricao']
            item = col1.selectbox("Selecione o Item", lista_p)
            
            qtd = col2.number_input("Quantidade Utilizada", min_value=0.01)
            ref = col2.text_input("Referência (Ex: Pedido de Saída)")
            
            if st.form_submit_button("Confirmar Saída"):
                nova_mov = pd.DataFrame([{
                    "tipo": "Saída", "data": str(data), "obra": obra, "sc": "", 
                    "mapa": "", "oc": ref, "codigo": item.split(" - ")[0], 
                    "descricao": item.split(" - ")[1], "quantidade": qtd
                }])
                mov_atualizada = pd.concat([df_mov, nova_mov], ignore_index=True)
                conn.update(worksheet="movimentacoes", data=mov_atualizada, spreadsheet=st.secrets["gsheets_url"])
                st.warning("Saída registrada!")

# --- HISTÓRICO ---
elif aba_selecionada == "📜 Histórico Geral":
    st.title("📜 Histórico de Movimentações")
    st.dataframe(df_mov, use_container_width=True, hide_index=True)
    st.download_button("Baixar Histórico (CSV)", df_mov.to_csv(index=False), "historico_estoque.csv")
