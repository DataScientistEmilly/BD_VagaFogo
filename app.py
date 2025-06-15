# --- 1. Importações de Bibliotecas ---
import os
from flask import Flask, request, jsonify, abort
import psycopg2
from dotenv import load_dotenv
from functools import wraps # Para o decorador do admin
from datetime import datetime, time, date # 

# --- 2. Carrega as Variáveis de Ambiente ---
# Isso deve ser feito logo no início para que as variáveis estejam disponíveis
load_dotenv()


app = Flask(__name__)

# - Configurações do Banco de Dados ---

DB_USER = os.getenv('DB_USER')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_PASSWORD =os.getenv('DB_PASSWORD')

def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados PostgreSQL.
    Usa as variáveis de ambiente para as credenciais.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=os.getenv('DB_PASSWORD'),
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
            
        )
        conn.set_client_encoding('UTF8')
        
        # apenas para verificar se a conexão com banco de dado foi feita
        print("Conectado ao banco de dados PostgreSQL!")
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        raise


#  será usado nas rotas que exigem permissão de administrador
def require_admin(f):
    """
   # acho que seja necessário a criação de um token de validação do administrador.

    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-User-Id') # Obtém o ID do usuário do cabeçalho da requisição

        if not user_id:
            
            abort(401, description="Autenticação necessária. ID do usuário (X-User-Id) não fornecido.")

        conn = None
        cur = None
        try:
            conn = get_db_connection() # Abre uma nova conexão para esta verificação
            cur = conn.cursor()
            cur.execute("SELECT is_admin FROM usuarios WHERE id = %s", (user_id,))
            user = cur.fetchone() 

            if not user:
                
                abort(404, description="Usuário não encontrado na base de dados de usuários da aplicação.")

            if user[0]:  # user[0] contém o valor booleano de is_admin
                return f(*args, **kwargs) # Usuário é administrador, permite prosseguir para a rota
            else:
                
                abort(403, description="Acesso negado. Você não tem permissão de administrador para esta ação.")
        except Exception as e:
            
            print(f"Erro ao verificar permissão de administrador: {e}")
            abort(500, description="Erro interno do servidor ao verificar permissões.")
        finally:
            
            if cur:
                cur.close()
            if conn:
                conn.close()
    return decorated_function




@app.route('/', methods=['GET'])
def home():
   
    return jsonify({"message": "Bem-vindo ao sistema de Reservas, você está pronto para uma experiencia completa!"})


@app.route('/usuarios', methods=['GET'])
def get_usuarios():
    
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, cpf, email, telefone, is_admin FROM usuarios ORDER BY id")
        usuarios = cur.fetchall() # Obtém todos os registros

        # Converte a lista de tuplas em uma lista de dicionários para JSON
        column_names = [desc[0] for desc in cur.description] # Obtém os nomes das colunas
        usuarios_dicts = [dict(zip(column_names, row)) for row in usuarios] # Cria dicionários
        return jsonify(usuarios_dicts)
    except Exception as e:
        print(f"Erro ao obter usuários: {e}")
        return jsonify({"message": "Erro interno do servidor ao buscar usuários."}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/usuarios', methods=['POST'])
def create_usuario():
    
    data = request.get_json()
    nome = data.get('nome')
    cpf = data.get('cpf')
    email = data.get('email')
    telefone = data.get('telefone')

    # Validação de entrada
    if not all([nome, cpf, email, telefone]):
        return jsonify({"message": "Todos os campos (nome, cpf, email, telefone) são obrigatórios."}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usuarios (nome, cpf, email, telefone) VALUES (%s, %s, %s, %s) RETURNING id, nome, cpf, email, telefone, is_admin",
            (nome, cpf, email, telefone)
        )
        new_user = cur.fetchone() 
        conn.commit() 

        column_names = [desc[0] for desc in cur.description]
        return jsonify(dict(zip(column_names, new_user))), 201 # Retorna o novo usuário com status 201 (Created)
    except psycopg2.errors.UniqueViolation:
        conn.rollback() # Reverte a transação em caso de erro de violação de unicidade
        return jsonify({"message": "CPF ou E-mail já cadastrado."}), 409 # Status 409 (Conflict)
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        if conn:
            conn.rollback()
        return jsonify({"message": "Erro interno do servidor ao criar usuário."}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/servicos', methods=['GET'])
def get_servicos():
    
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, valor, capacidade_maxima, horarios_fixos, horario_inicio_diario, horario_fim_diario FROM servicos ORDER BY id")
        servicos = cur.fetchall()

        column_names = [desc[0] for desc in cur.description]
        servicos_dicts = [dict(zip(column_names, row)) for row in servicos]
        return jsonify(servicos_dicts)
    except Exception as e:
        print(f"Erro ao obter serviços: {e}")
        return jsonify({"message": "Erro interno do servidor ao buscar serviços."}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/servicos', methods=['POST'])
@require_admin # APENAS ADMINISTRADORES PODEM CRIAR SERVIÇOS
def create_servico():
    
    data = request.get_json()
    nome = data.get('nome')
    valor = data.get('valor')
    # Novas colunas que podem ser enviadas ao criar um serviço (opcional)
    capacidade_maxima = data.get('capacidade_maxima')
    horarios_fixos = data.get('horarios_fixos') # Esperado como uma lista de strings de tempo ex: ["09:00:00", "11:00:00"]
    horario_inicio_diario = data.get('horario_inicio_diario') # Esperado como string de tempo ex: "09:00:00"
    horario_fim_diario = data.get('horario_fim_diario') # Esperado como string de tempo ex: "16:00:00"

    if not nome or valor is None: 
        return jsonify({"message": "Nome e valor do serviço são obrigatórios."}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO servicos (nome, valor, capacidade_maxima, horarios_fixos, horario_inicio_diario, horario_fim_diario)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, nome, valor, capacidade_maxima, horarios_fixos, horario_inicio_diario, horario_fim_diario
            """,
            (nome, valor, capacidade_maxima, horarios_fixos, horario_inicio_diario, horario_fim_diario)
        )
        new_service = cur.fetchone()
        conn.commit()

        column_names = [desc[0] for desc in cur.description]
        return jsonify(dict(zip(column_names, new_service))), 201
    except Exception as e:
        print(f"Erro ao criar serviço: {e}")
        if conn:
            conn.rollback()
        return jsonify({"message": "Erro interno do servidor ao criar serviço."}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()



@app.route('/reservas', methods=['POST'])
def create_reserva():

    data = request.get_json()
    usuario_id = data.get('usuario_id')
    servico_id = data.get('servico_id')
    data_agendamento_str = data.get('data_agendamento') # String da data/hora (ex: '2025-07-20 09:00:00')
    quantidade_pessoas = data.get('quantidade_pessoas')
    quantidade_criancas = data.get('quantidade_criancas', 0)
    quantidade_bariatricos = data.get('quantidade_bariatricos', 0)

    try:
        quantidade_pessoas = int(quantidade_pessoas)
    except (ValueError, TypeError):
        return jsonify({"erro": "O campo 'quantidade_pessoas' deve ser um número inteiro válido."}), 400


    try:
        quantidade_criancas = int(quantidade_criancas)
    except (ValueError, TypeError):
        return jsonify({"erro": "O campo 'quantidade_criancas' deve ser um número inteiro válido."}), 400


    try:
        quantidade_bariatricos = int(quantidade_bariatricos)
    except (ValueError, TypeError):
        return jsonify({"erro": "O campo 'quantidade_bariatricos' deve ser um número inteiro válido."}), 400

#  Validação de Campos Obrigatórios
    if not all([usuario_id, servico_id, data_agendamento_str, quantidade_pessoas]):
        return jsonify({"message": "Campos obrigatórios: usuario_id, servico_id, data_agendamento, quantidade_pessoas."}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        #  Obter Informações do Serviço e Validar IDs
        cur.execute(
            "SELECT nome, capacidade_maxima, horarios_fixos, horario_inicio_diario, horario_fim_diario FROM servicos WHERE id = %s",
            (servico_id,)
        )
        servico = cur.fetchone()

        if not servico:
            return jsonify({"message": "Serviço não encontrado."}), 400

        servico_nome, capacidade_maxima, horarios_fixos_db, horario_inicio_diario_db, horario_fim_diario_db = servico

        #  Extrair e validar a data e hora da string de agendamento
        try:
            # Tenta converter a string para datetime. Se não houver hora, será 00:00:00.
            # Aceita 'YYYY-MM-DD' ou 'YYYY-MM-DD HH:MM:SS'
            if ' ' in data_agendamento_str:
                data_agendamento_dt = datetime.strptime(data_agendamento_str, '%Y-%m-%d %H:%M:%S')
            else:
                data_agendamento_dt = datetime.strptime(data_agendamento_str, '%Y-%m-%d')
            
            data_reserva = data_agendamento_dt.date()
            hora_reserva = data_agendamento_dt.time()
        except ValueError:
            return jsonify({"message": "Formato de 'data_agendamento' inválido. Use 'AAAA-MM-DD HH:MM:SS' ou 'AAAA-MM-DD'."}), 400


        # Regras para BRUNCH 
        if servico_nome == 'Brunch':
            # Valida horário fixo
            # Converte os horários do banco (que vêm como datetime.time) para string para comparação
            horarios_permitidos_str = [h.strftime('%H:%M:%S') for h in horarios_fixos_db] if horarios_fixos_db else []
            if hora_reserva.strftime('%H:%M:%S') not in horarios_permitidos_str:
                return jsonify({"message": f"Horário para Brunch inválido. Apenas {', '.join(horarios_permitidos_str)} são permitidos."}), 400

            # Valida capacidade máxima para o horário
            if capacidade_maxima is not None:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(quantidade_pessoas), 0)
                    FROM reservas
                    WHERE servico_id = %s
                      AND data_agendamento::date = %s -- Compara apenas a data
                      AND data_agendamento::time = %s -- Compara apenas a hora
                    """,
                    (servico_id, data_reserva, hora_reserva)
                )
                pessoas_ja_reservadas = cur.fetchone()[0] or 0 # COALESCE garante 0 se não houver reservas

                if (pessoas_ja_reservadas + quantidade_pessoas) > capacidade_maxima:
                    return jsonify({"message": f"Limite de {capacidade_maxima} pessoas para o Brunch excedido neste horário. Já existem {pessoas_ja_reservadas} pessoas agendadas."}), 400

        #  Regras para TRILHA 
        elif servico_nome == 'Trilha':
            
            if horario_inicio_diario_db and horario_fim_diario_db:
                
                if not (horario_inicio_diario_db <= hora_reserva <= horario_fim_diario_db):
                    return jsonify({"message": f"Horário para Trilha inválido. Deve ser entre {horario_inicio_diario_db.strftime('%H:%M')} e {horario_fim_diario_db.strftime('%H:%M')}."}), 400
                

        #  Insere a Reserva se Todas as Validações Passarem
        cur.execute(
            """
            INSERT INTO reservas (usuario_id, servico_id, data_agendamento, quantidade_pessoas, quantidade_criancas, quantidade_bariatricos)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, usuario_id, servico_id, data_agendamento, quantidade_pessoas, quantidade_criancas, quantidade_bariatricos
            """,
            (usuario_id, servico_id, data_agendamento_dt, quantidade_pessoas, quantidade_criancas, quantidade_bariatricos)
        )
        new_reserva = cur.fetchone()
        conn.commit()

        column_names = [desc[0] for desc in cur.description]
        return jsonify(dict(zip(column_names, new_reserva))), 201
    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback() # Reverte em caso de IDs de usuário ou serviço inválidos
        return jsonify({"message": "Usuário ou serviço não encontrado. Verifique os IDs."}), 400
    except Exception as e:
        print(f"Erro ao criar reserva: {e}")
        if conn:
            conn.rollback()
        return jsonify({"message": "Erro interno do servidor ao criar reserva."}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
   

    return jsonify({"message": "Reserva criada com sucesso!"}), 201


    # Saída das reservas
    reservas = []
    for row in rows:
        reservas.append({
            "id": row[0],
            "nome": row[1],
            "cpf": row[2],
            "email": row[3],
            "telefone": row[4],
            "servico": row[5],
            "qtd_pessoas": row[6],
            "qtd_criancas": row[7],
            "qtd_bariatricos": row[8],
            "data_agendamento": str(row[9])
        })

    return jsonify(reservas)



#  Inicialização da Aplicação 
# Isso garante que o servidor Flask só inicie quando o script for executado diretamente
if __name__ == '__main__':
    # debug=True: recarrega o servidor automaticamente ao salvar e mostra erros detalhados
    # port=5000: Define a porta em que a API será executada
    app.run(debug=True, port=5000)
