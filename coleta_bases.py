"""
Coleta automatizada das três fontes do projeto de enchentes.
Salva arquivos brutos em dados/originais e um CSV filtrado para Porto Alegre e Taquara.

Instalação:
    pip install requests beautifulsoup4 pandas

Execução:
    python coleta_bases.py
"""

from pathlib import Path
from datetime import datetime
import re
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
PASTA = BASE_DIR / "dados" / "originais"
PASTA.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "ProjetoAcademico-Enchentes/1.0 (coleta para fins educacionais)"
}
TIMEOUT = 90


def baixar(url, destino):
    """Baixa um arquivo e salva no caminho informado."""
    print(f"Baixando: {url}")
    resposta = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
    resposta.raise_for_status()
    with open(destino, "wb") as arquivo:
        for parte in resposta.iter_content(chunk_size=1024 * 1024):
            if parte:
                arquivo.write(parte)
    print(f"Salvo em: {destino}")


def coletar_zenodo():
    """
    Consulta o registro do Zenodo pela API e baixa o CSV de glossário.
    Também baixa o GeoPackage principal quando ele estiver listado no registro.
    """
    api = "https://zenodo.org/api/records/12593168"
    resposta = requests.get(api, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()
    registro = resposta.json()

    (PASTA / "zenodo_metadados.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    arquivos = registro.get("files", [])
    print("\nArquivos encontrados no Zenodo:")
    for item in arquivos:
        nome = item.get("key", "")
        link = item.get("links", {}).get("self")
        print("-", nome)

        # Glossário CSV: arquivo pequeno e útil para identificar as camadas.
        if "glossario" in nome.lower() and nome.lower().endswith(".csv") and link:
            baixar(link, PASTA / "zenodo_glossario.csv")

        # GeoPackage principal: contém as camadas geográficas do estudo.
        if nome.lower().endswith(".gpkg") and "cheias_rhguaiba_2024_db" in nome.lower() and link:
            baixar(link, PASTA / nome)

    if not arquivos:
        print("A API não retornou arquivos. Confira a versão do registro no Zenodo.")


def coletar_atlas():
    """
    Lê a página pública de downloads do Atlas, localiza o link CSV e baixa a base.
    O site pode bloquear a requisição automatizada; nesse caso, use o link manual
    indicado na mensagem de erro.
    """
    pagina = "https://atlasdigital.mdr.gov.br/paginas/downloads.xhtml"
    resposta = requests.get(pagina, headers=HEADERS, timeout=TIMEOUT)
    resposta.raise_for_status()

    soup = BeautifulSoup(resposta.text, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        texto = a.get_text(" ", strip=True).lower()
        if ".csv" in href.lower() or "csv" in texto:
            links.append(requests.compat.urljoin(pagina, href))

    if not links:
        # Fallback: procura URLs CSV no HTML bruto.
        encontrados = re.findall(r"""(?:https?://[^"' ]+|/[^"' ]+)\.csv[^"' ]*""",
                                 resposta.text, flags=re.I)
        links = [requests.compat.urljoin(pagina, x) for x in encontrados]

    if not links:
        raise RuntimeError(
            "Não encontrei o link CSV automaticamente. Abra "
            "https://atlasdigital.mdr.gov.br/paginas/downloads.xhtml e baixe "
            "a opção 'Ponto e Vírgula (CSV) - Apenas Valores Corrigidos' "
            "para dados/originais/atlas_desastres.csv."
        )

    url_csv = links[0]
    baixar(url_csv, PASTA / "atlas_desastres.csv")
    (PASTA / "atlas_url_coleta.txt").write_text(url_csv, encoding="utf-8")


def coletar_smamus():
    """
    Consulta uma camada pública da SMAMUS via ArcGIS REST.
    A camada representa cotas de inundação entre 3 m e 5,35 m.
    Retorna os polígonos em GeoJSON.
    """
    url = (
        "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/"
        "01_PUBLICACOES/cotas_inundacao_300_535/FeatureServer/0/query"
    )
    parametros = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson"
    }

    resposta = requests.get(
        url, params=parametros, headers=HEADERS, timeout=TIMEOUT
    )
    resposta.raise_for_status()
    dados = resposta.json()

    destino = PASTA / "smamus_cotas_inundacao.geojson"
    destino.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Camada SMAMUS salva em: {destino}")


def filtrar_atlas_rs():
    """
    Gera uma cópia filtrada do CSV do Atlas para RS, Porto Alegre e Taquara.
    Mantém a base original intacta.
    """
    arquivo = PASTA / "atlas_desastres.csv"
    if not arquivo.exists():
        print("CSV do Atlas não encontrado; filtro não executado.")
        return

    # O Atlas informa que o CSV usa ponto e vírgula.
    df = pd.read_csv(arquivo, sep=";", encoding="utf-8", low_memory=False)
    print("\nColunas do Atlas:", list(df.columns))

    # Filtra primeiro pelo RS, se existir coluna de UF.
    col_uf = next((c for c in df.columns if c.strip().lower() in
                   ["uf", "estado", "sigla_uf"]), None)
    if col_uf:
        df = df[df[col_uf].astype(str).str.upper().str.strip().isin(["RS", "RIO GRANDE DO SUL"])]

    # Procura a coluna que contém o município.
    col_mun = next((c for c in df.columns if "munic" in c.lower()), None)
    if col_mun:
        municipios = df[col_mun].astype(str).str.normalize("NFKD").str.encode(
            "ascii", errors="ignore"
        ).str.decode("ascii").str.upper().str.strip()
        df = df[municipios.isin(["PORTO ALEGRE", "TAQUARA"])]

    saida = PASTA / "atlas_porto_alegre_taquara.csv"
    df.to_csv(saida, sep=";", index=False, encoding="utf-8-sig")
    print(f"Base filtrada salva em: {saida}")
    print("Registros filtrados:", len(df))


def main():
    coleta_em = datetime.now().astimezone().isoformat(timespec="seconds")
    print("Início da coleta:", coleta_em)

    tarefas = [
        ("Zenodo", coletar_zenodo),
        ("Atlas Digital", coletar_atlas),
        ("SMAMUS", coletar_smamus),
    ]

    for nome, funcao in tarefas:
        print(f"\n===== {nome} =====")
        try:
            funcao()
        except Exception as erro:
            print(f"Não foi possível concluir {nome}: {erro}")

    filtrar_atlas_rs()
    (PASTA / "coleta_info.json").write_text(
        json.dumps(
            {
                "coleta_em": coleta_em,
                "fontes": {
                    "zenodo": "https://zenodo.org/records/12593168",
                    "atlas_digital": "https://atlasdigital.mdr.gov.br/paginas/downloads.xhtml",
                    "smamus": "https://gis-smamus.portoalegre.rs.gov.br/server/rest/services/01_PUBLICACOES/cotas_inundacao_300_535/FeatureServer/0",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nColeta finalizada. Confira a pasta:", PASTA.resolve())


if __name__ == "__main__":
    main()
