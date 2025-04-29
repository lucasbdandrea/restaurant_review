from typing import Dict, List, Tuple
from autogen import ConversableAgent
from dotenv import load_dotenv
import sys
import os
import math
import ast

# Carrega variáveis do .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def fetch_restaurant_data(restaurant_name: str) -> Dict[str, List[str]]:
    # TODO
    # Esta função recebe o nome de um restaurante e retorna as avaliações desse restaurante.
    # A saída deve ser um dicionário, onde a chave é o nome do restaurante e o valor é uma lista de avaliações desse restaurante.
    # O "agente de busca de dados" deve ter acesso à assinatura desta função e deve ser capaz de sugeri-la como uma chamada de função.
    # Exemplo:
    # > fetch_restaurant_data("Estação Barão")
    # {"Estação Barão's": ["A comida do Estação Barão foi mediana, sem nada particularmente marcante.", ...]}
    reviews = []
    try:
        with open("restaurantes.txt", "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue

                parts = line.split(". ", 1)
                if len(parts) != 2:
                    continue

                current_name, review = parts
                if current_name.lower() == restaurant_name.lower():
                    reviews.append(review)
    except FileNotFoundError:
        print("Arquivo de dados de restaurantes não encontrado.")
        return {}

    return {restaurant_name: reviews} if reviews else {}


def calculate_overall_score(restaurant_name: str, food_scores: List[int], customer_service_scores: List[int]) -> Dict[str, float]:
    # TODO
    # Esta função recebe o nome de um restaurante, uma lista de notas da comida (de 1 a 5) e uma lista de notas do atendimento ao cliente (de 1 a 5).
    # A saída deve ser uma pontuação entre 0 e 10, calculada da seguinte forma:
    # SUM(sqrt(food_scores[i]**2 * customer_service_scores[i]) * 1/(N * sqrt(125)) * 10
    # A fórmula acima é uma média geométrica das notas, que penaliza mais a qualidade da comida do que o atendimento ao cliente.
    # Exemplo:
    # > calculate_overall_score("Applebee's", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    # {"Applebee's": 5.048}
    # OBSERVAÇÃO: Certifique-se de que a pontuação inclui PELO MENOS 3 casas decimais. Os testes públicos só aceitarão pontuações
    # que tenham no mínimo 3 casas decimais.
    if not food_scores or not customer_service_scores:
        return {restaurant_name: 0.0}

    # Garante que as listas tenham o mesmo tamanho
    N = min(len(food_scores), len(customer_service_scores))
    food_scores = food_scores[:N]
    customer_service_scores = customer_service_scores[:N]

    total = 0.0
    for food, service in zip(food_scores, customer_service_scores):
        term = math.sqrt(food**2 * service)
        total += term

    score = (total * 10) / (N * math.sqrt(125)) if N > 0 else 0.0
    return {restaurant_name: round(score, 3)}


def parse_scores_from_analysis(analysis_output: str) -> Tuple[List[int], List[int]]:
    """Extrai as pontuações da saída do agente de análise."""
    try:
        # Procura por padrões como [1, 2, 3], [4, 5]
        parts = analysis_output.split("], [")
        if len(parts) != 2:
            return [], []

        food_part = parts[0].replace("[", "").strip()
        service_part = parts[1].replace("]", "").strip()

        food_scores = [int(x.strip())
                       for x in food_part.split(",") if x.strip().isdigit()]
        service_scores = [int(x.strip())
                          for x in service_part.split(",") if x.strip().isdigit()]

        return food_scores, service_scores
    except Exception:
        return [], []


def execute_function_call(function_call: str) -> str:
    """Executa uma chamada de função sugerida pelo agente."""
    try:
        # Usa AST para interpretar de forma segura os argumentos
        tree = ast.parse(function_call.strip(), mode='eval')
        if not isinstance(tree.body, ast.Call):
            return "Erro: chamada de função inválida."

        func_name = tree.body.func.id
        func = globals().get(func_name)
        if not func:
            return f"Erro: Função {func_name} não encontrada"

        # Avalia argumentos
        args = [ast.literal_eval(arg) for arg in tree.body.args]
        kwargs = {kw.arg: ast.literal_eval(kw.value)
                  for kw in tree.body.keywords}

        # Executa a função
        result = func(*args, **kwargs)
        return str(result)
    except Exception as e:
        return f"Erro ao executar função: {str(e)}"


def main(user_query: str):
    # Configuração do LLM
    llm_config = {
        "config_list": [
            {
                "model": "gpt-3.5-turbo",
                "api_key": OPENAI_API_KEY,
            }
        ],
        "temperature": 0.3,
        "timeout": 60
    }

    # 1. data_fetch_agent - Responsável por recuperar avaliações
    data_fetch_agent = ConversableAgent(
        "data_fetch_agent",
        system_message="""Você é responsável por recuperar avaliações de restaurantes.
        
        Suas tarefas:
        1. Extrair o nome do restaurante da consulta do usuário
           - Remova artigos/preposições iniciais ('o', 'a', 'do', 'da')
           - Mantenha preposições internas e capitalização
           - Exemplo: "Qual a avaliação do Casa do Pão de Queijo?" → "Casa do Pão de Queijo"
        
        2. Sugerir a chamada da função fetch_restaurant_data com o nome extraído
           - Formato: fetch_restaurant_data(restaurant_name='Nome do Restaurante')
        
        Retorne APENAS a chamada de função sugerida.""",
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2
    )

    # Agente de Análise de Revisões
    review_analysis_agent = ConversableAgent(
        "review_analyst",
        system_message="""Você é um analista especializado em avaliações de restaurantes. 
        Extraia pontuações para COMIDA e ATENDIMENTO seguindo estas regras:
        
        1. Critérios de Pontuação (1-5):
        - 1: horrível, nojento, terrível
        - 2: ruim, desagradável
        - 3: mediano, sem graça
        - 4: bom, agradável
        - 5: incrível, excelente
        
        2. Associe adjetivos a:
        - COMIDA: "comida", "prato", "sabor", "ingredientes"
        - ATENDIMENTO: "atendimento", "serviço", "garçons"
        
        3. Formato de saída EXATO:
        [scores_comida], [scores_atendimento]
        
        Exemplos:
        Input: "Comida mediana e atendimento incrível."
        Output: [3], [5]
        
        Input: "Hambúrguer nojento e serviço desagradável."
        Output: [1], [2]""",
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2
    )



    # 3. score_agent - Responsável pelo cálculo final da pontuação
    score_agent = ConversableAgent(
        "score_agent",
        system_message="""Você é responsável pelo cálculo final da pontuação do restaurante.
        
        Suas tarefas:
        1. Receber as pontuações de comida e atendimento
        2. Sugerir a chamada da função calculate_overall_score com:
           - restaurant_name: nome do restaurante
           - food_scores: lista de pontuações de comida
           - customer_service_scores: lista de pontuações de atendimento
        
        Formato:
        calculate_overall_score(restaurant_name='Nome', food_scores=[...], customer_service_scores=[...])
        
        Retorne APENAS a chamada de função sugerida.""",
        llm_config=llm_config,
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2
    )

    # 4. supervisor_agent - Controla o fluxo do pipeline
    supervisor_agent = ConversableAgent(
        "supervisor_agent",
        system_message="""Você é o supervisor do pipeline de avaliação de restaurantes. 
        Seu trabalho é orquestrar o fluxo de processamento e garantir que cada etapa seja executada corretamente.
        
        Fluxo de trabalho:
        1. Receber a consulta do usuário
        2. Enviar para o data_fetch_agent extrair o nome do restaurante e buscar avaliações
        3. Enviar as avaliações para o review_analysis_agent extrair pontuações
        4. Enviar as pontuações para o score_agent calcular a nota final
        5. Verificar os resultados em cada etapa e tomar decisões em caso de erros
        
        Em caso de erro em qualquer etapa:
        - Se não encontrar avaliações: retorne "Nenhuma avaliação encontrada para [nome_restaurante]"
        - Se não conseguir extrair pontuações: retorne "Não foi possível analisar as avaliações"
        - Se não conseguir calcular a pontuação final: retorne "Erro no cálculo da pontuação"
        
        Em caso de sucesso:
        - Retorne a pontuação final no formato: "A pontuação do [nome_restaurante] é: X.XXX"
        """,
        llm_config=llm_config,
        human_input_mode="NEVER",
        # Permite mais interações para supervisionar todo o fluxo
        max_consecutive_auto_reply=6
    )

    # Fluxo principal controlado pelo supervisor
    try:
        # Inicia a conversa com o supervisor
        final_result = supervisor_agent.initiate_chat(
            recipient=data_fetch_agent,
            message=user_query,
            max_turns=1
        )

        # Obtém a resposta do data_fetch_agent
        function_call = final_result.chat_history[-1]["content"]

        if not function_call or "fetch_restaurant_data" not in function_call:
            print("Erro: Não foi possível identificar o nome do restaurante.")
            return

        # Executa a chamada de função
        reviews_data_str = execute_function_call(function_call)
        reviews_data = eval(
            reviews_data_str) if reviews_data_str.startswith("{") else None

        if not reviews_data:
            print(f"Nenhuma avaliação encontrada para o restaurante.")
            return

        restaurant_name = next(iter(reviews_data.keys()))
        reviews = reviews_data[restaurant_name]

        # Envia as avaliações para análise
        analysis_result = supervisor_agent.initiate_chat(
            recipient=review_analysis_agent,
            message="\n".join(reviews),
            max_turns=1
        )

        analysis_output = analysis_result.chat_history[-1]["content"]
        food_scores, service_scores = parse_scores_from_analysis(
            analysis_output)

        if not food_scores or not service_scores:
            print("Erro: Não foi possível extrair pontuações das avaliações.")
            return

        # Prepara os dados para cálculo do score
        score_input = {
            "restaurant_name": restaurant_name,
            "food_scores": food_scores,
            "customer_service_scores": service_scores
        }

        # Envia para cálculo final
        final_score_call = supervisor_agent.initiate_chat(
            recipient=score_agent,
            message=str(score_input),
            max_turns=1
        )

        function_call = final_score_call.chat_history[-1]["content"]

        if not function_call or "calculate_overall_score" not in function_call:
            print("Erro: Não foi possível calcular a pontuação final.")
            return

        # Executa a chamada de função final
        final_score_str = execute_function_call(function_call)
        final_score = eval(
            final_score_str) if final_score_str.startswith("{") else None

        # Resultado formatado
        if final_score and restaurant_name in final_score:
            print(
                f"A pontuação do {restaurant_name} é: {final_score[restaurant_name]:.3f}")
        else:
            print("Erro: Não foi possível calcular a pontuação final.")

    except Exception as e:
        print(f"Erro no processamento: {str(e)}")
        return


if __name__ == "__main__":
    assert len(
        sys.argv) > 1, "Certifique-se de incluir uma consulta para algum restaurante ao executar a função main."
    main(sys.argv[1])
