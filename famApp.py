import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import os

# --- Configuração da Página ---
st.set_page_config(page_title="Organizador de Encontros Familiares", layout="wide")

# --- Constantes e Configurações Globais ---
DATA_FILE = 'dados_evento.json'
DIAS_NOTIFICACAO = 14
DIAS_PAGAMENTO = 7

# --- Funções de Gerenciamento de Dados ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "evento": {"data": None, "custo_por_pessoa": 0.0, "nome": ""},
            "agregados": [],
            "confirmacoes": {} # Key: nome_agregado, Value: {'qtd_pessoas': int, 'confirmado': bool}
        }
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def init_session():
    if 'data' not in st.session_state:
        st.session_state.data = load_data()

# --- Lógica de Negócio ---
def calcular_estatisticas(dados):
    if not dados['evento']['data']:
        return None
    
    data_evento = datetime.strptime(dados['evento']['data'], "%Y-%m-%d")
    hoje = datetime.now().date()
    dias_restantes = (data_evento.date() - hoje).days
    
    total_pessoas = sum([c['qtd_pessoas'] for c in dados['confirmacoes'].values() if c['confirmado']])
    custo_total = total_pessoas * dados['evento']['custo_por_pessoa']
    
    # Cálculo por agregado
    detalhes_agregados = []
    for agg in dados['agregados']:
        nome = agg['nome']
        conf = dados['confirmacoes'].get(nome, {'qtd_pessoas': 0, 'confirmado': False})
        
        qtd = conf['qtd_pessoas'] if conf['confirmado'] else 0
        custo_agg = qtd * dados['evento']['custo_por_pessoa']
        
        detalhes_agregados.append({
            "Agregado": nome,
            "Responsável": agg['responsavel'],
            "Confirmado": "Sim" if conf['confirmado'] else "Não",
            "Qtd Pessoas": qtd,
            "Custo Estimado (€)": custo_agg
        })
        
    df = pd.DataFrame(detalhes_agregados)
    
    return {
        "dias_restantes": dias_restantes,
        "total_pessoas": total_pessoas,
        "custo_total": custo_total,
        "df_detalhes": df,
        "pode_confirmar": dias_restantes <= DIAS_NOTIFICACAO and dias_restantes >= 0,
        "pode_pagar": dias_restantes <= DIAS_PAGAMENTO and dias_restantes >= 0
    }

# --- Interface do Usuário ---

def main():
    init_session()
    dados = st.session_state.data
    stats = calcular_estatisticas(dados)
    
    st.title("🍲 Gestor de Encontros de Família")
    
    # Menu Lateral
    menu = st.sidebar.selectbox("Menu", ["Configurar Evento", "Gerir Agregados", "Área dos Convidados (Confirmação)", "Resumo Financeiro"])
    
    # 1. Configurar Evento
    if menu == "Configurar Evento":
        st.header("Definição do Evento")
        col1, col2 = st.columns(2)
        
        with col1:
            nome_evento = st.text_input("Nome do Evento", value=dados['evento']['nome'])
            data_evento = st.date_input("Data do Encontro", value=datetime.strptime(dados['evento']['data'], "%Y-%m-%d") if dados['evento']['data'] else datetime.now())
        
        with col2:
            custo_unit = st.number_input("Custo estimado por pessoa (Comida + Bebida)", min_value=0.0, step=5.0, value=dados['evento']['custo_por_pessoa'])
        
        if st.button("Salvar Configurações"):
            dados['evento']['nome'] = nome_evento
            dados['evento']['data'] = str(data_evento)
            dados['evento']['custo_por_pessoa'] = custo_unit
            save_data(dados)
            st.success("Evento configurado com sucesso!")
            st.rerun()

    # 2. Gerir Agregados (Admin)
    elif menu == "Gerir Agregados":
        st.header("Lista de Casas / Agregados")
        
        # Formulário para adicionar
        with st.form("add_agg"):
            c1, c2 = st.columns(2)
            nome_casa = c1.text_input("Nome da Casa/Família (ex: Casa do Tio João)")
            resp = c2.text_input("Nome do Responsável")
            submitted = st.form_submit_button("Adicionar Agregado")
            
            if submitted and nome_casa and resp:
                if not any(a['nome'] == nome_casa for a in dados['agregados']):
                    dados['agregados'].append({"nome": nome_casa, "responsavel": resp})
                    dados['confirmacoes'][nome_casa] = {"qtd_pessoas": 0, "confirmado": False}
                    save_data(dados)
                    st.success(f"{nome_casa} adicionado!")
                    st.rerun()
                else:
                    st.error("Este agregado já existe.")
        
        # Lista existente
        st.subheader("Agregados Cadastrados")
        if dados['agregados']:
            df_list = pd.DataFrame(dados['agregados'])
            st.table(df_list)
        else:
            st.info("Nenhum agregado cadastrado.")

    # 3. Área dos Convidados (Simulação de Login por Nome da Casa)
    elif menu == "Área dos Convidados (Confirmação)":
        st.header("Confirmação de Presença")
        
        if not stats:
            st.warning("Configure a data do evento primeiro.")
            return

        if not stats['pode_confirmar']:
            st.warning(f"A confirmação só estará disponível a partir de {DIAS_NOTIFICACAO} semanas antes do evento.")
            st.info(f"Faltam {stats['dias_restantes']} dias para o evento.")
            return

        st.success(f"O evento '{dados['evento']['nome']}' está confirmado para {dados['evento']['data']}!")
        
        selected_agg_name = st.selectbox("Selecione a sua Casa/Agregado", [a['nome'] for a in dados['agregados']])
        
        if selected_agg_name:
            current_conf = dados['confirmacoes'].get(selected_agg_name, {"qtd_pessoas": 0, "confirmado": False})
            
            col1, col2 = st.columns(2)
            with col1:
                confirmar = st.checkbox("Vou comparecer", value=current_conf['confirmado'])
            with col2:
                qtd_pessoas = st.number_input("Quantas pessoas da sua casa irão?", min_value=1, value=current_conf['qtd_pessoas'] if current_conf['qtd_pessoas'] > 0 else 1, disabled=not confirmar)
            
            if st.button("Enviar Confirmação"):
                dados['confirmacoes'][selected_agg_name] = {
                    "qtd_pessoas": qtd_pessoas if confirmar else 0,
                    "confirmado": confirmar
                }
                save_data(dados)
                st.success("Confirmação recebida com sucesso!")
                st.rerun()

    # 4. Resumo Financeiro e Logística
    elif menu == "Resumo Financeiro":
        st.header("Apuramento Final")
        
        if not stats:
            st.warning("Configure o evento primeiro.")
            return
            
        st.metric("Dias Restantes", stats['dias_restantes'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Pessoas Confirmadas", stats['total_pessoas'])
        col2.metric("Custo Total Estimado", f"€ {stats['custo_total']:.2f}")
        col3.metric("Custo por Pessoa", f"€ {dados['evento']['custo_por_pessoa']:.2f}")
        
        st.divider()
        
        st.subheader("Detalhe por Agregado")
        st.dataframe(stats['df_detalhes'], use_container_width=True)
        
        # Regra de Pagamento
        st.divider()
        if stats['pode_pagar']:
            st.error("⚠️ ATENÇÃO: Faltam menos de uma semana! É necessário realizar os pagamentos agora.")
            st.write("Valores a transferir por cada agregado:")
            
            # Formatar tabela de pagamento
            df_pay = stats['df_detalhes'][['Agregado', 'Custo Estimado (€)']]
            df_pay = df_pay.rename(columns={"Custo Estimado (€)": "Valor a Pagar (€)"})
            st.table(df_pay)
            
            total_a_receber = df_pay['Valor a Pagar (€)'].sum()
            st.info(f"Total esperado em conta: € {total_a_receber:.2f}")
        else:
            st.info(f"O cálculo dos valores a pagar será liberado quando faltarem {DIAS_PAGAMENTO} dias ou menos para o evento.")

if __name__ == "__main__":
    main()