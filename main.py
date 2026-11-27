"""Dashboard acadêmico sobre vias p atingidas pela enchente de 2024."""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyogrio
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dados" / "originais"
INCT_JSON = ROOT / "dados" / "inct_simulacao.json"
FLOOD_URL = "https://zenodo.org/records/12593168/files/cheias_rhguaiba_2024_db_v11.gpkg?download=1"
ROADS_URL = "https://zenodo.org/records/12593168/files/insumos_openstreetmaps_vias_rhguaiba.gpkg?download=1"
HEADERS = {"User-Agent": "ProjetoAcademico-Enchentes/1.0 (uso educacional)"}
ROAD_LABELS = {
    "motorway": "Rodovia principal", "motorway_link": "Acesso à rodovia principal",
    "trunk": "Rodovia ou via expressa", "trunk_link": "Acesso à via expressa",
    "primary": "Via arterial principal", "primary_link": "Acesso à via arterial principal",
    "secondary": "Via arterial secundária", "secondary_link": "Acesso à via arterial secundária",
    "tertiary": "Via coletora", "tertiary_link": "Acesso à via coletora",
    "residential": "Rua residencial", "unclassified": "Via local sem classificação",
    "service": "Via de serviço ou acesso", "living_street": "Rua compartilhada",
    "pedestrian": "Via de pedestres", "track": "Estrada rural", "path": "Trilha ou caminho",
    "footway": "Caminho de pedestres", "cycleway": "Ciclovia", "steps": "Escadaria",
    "road": "Via sem classificação",
}
ROAD_GROUPS = {
    "motorway": "Rodovias e vias principais", "motorway_link": "Rodovias e vias principais",
    "trunk": "Rodovias e vias principais", "trunk_link": "Rodovias e vias principais",
    "primary": "Rodovias e vias principais", "primary_link": "Rodovias e vias principais",
    "secondary": "Vias secundárias e coletoras", "secondary_link": "Vias secundárias e coletoras",
    "tertiary": "Vias secundárias e coletoras", "tertiary_link": "Vias secundárias e coletoras",
    "residential": "Ruas locais e residenciais", "unclassified": "Ruas locais e residenciais",
    "living_street": "Ruas locais e residenciais",
    "service": "Vias de serviço e acessos",
    "cycleway": "Ciclovias",
    "footway": "Caminhos de pedestres", "pedestrian": "Caminhos de pedestres",
    "path": "Trilhas e caminhos", "track": "Estradas rurais", "steps": "Escadarias",
}

st.set_page_config(
    page_title="Enchente 2024 | Impacto nas vias",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)
px.defaults.template = "plotly_white"

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --ink:#102a36; --muted:#637984; --teal:#087e83; --aqua:#dff3ef; --paper:#f5f8f7; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    h1,h2,h3 { font-family:'Manrope',sans-serif !important; letter-spacing:-.035em; color:var(--ink); }
    [data-testid="stSidebar"] { background:#102a36; }
    [data-testid="stSidebar"] * { color:#eaf4f3 !important; }
    .hero { padding:1.35rem 1.55rem; border-radius:18px; color:#fff; background:linear-gradient(120deg,#0d3440 0%,#087e83 100%); margin:.3rem 0 1.4rem; }
    .hero h1 { color:#fff !important; margin:0; font-size:2rem; }
    .hero p { margin:.4rem 0 0; color:#d6eeeb; font-size:1rem; }
    .eyebrow { text-transform:uppercase; letter-spacing:.13em; font-size:.72rem; font-weight:700; color:#b5e6df; margin-bottom:.35rem; }
    .note { border-left:4px solid #e6a847; background:#fff8e9; padding:.8rem 1rem; border-radius:4px 12px 12px 4px; color:#5a4930; }
    .source { color:var(--muted); font-size:.82rem; }
    div[data-testid="stMetric"] { background:#fff; border:1px solid #e5ecea; padding:1rem 1.1rem; border-radius:14px; box-shadow:0 3px 12px rgba(16,42,54,.035); }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] *, [data-testid="stMetricLabel"] { color:#000000 !important; -webkit-text-fill-color:#000000 !important; opacity:1 !important; font-weight:700; font-size:1rem; }
    div[data-testid="stMetricValue"] { color:#081f2b !important; font-family:'Manrope',sans-serif; font-weight:800; }
    div[data-testid="stSelectbox"] label, div[data-testid="stSelectbox"] p { color:#102a36 !important; font-weight:700; }
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div { background:#fff; color:#102a36; border-color:#9aafb2; }
    div[data-testid="stSlider"] label, div[data-testid="stSlider"] label p, div[data-testid="stSlider"] label span { color:#000000 !important; -webkit-text-fill-color:#000000 !important; opacity:1 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def br_num(value: float | int, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def normalize_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def read_inct_json(path: Path = INCT_JSON) -> pd.DataFrame:
    """Lê o formato hierárquico nível -> bairro usado no arquivo enviado."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for level_key, neighborhoods in raw.items():
        match = re.search(r"\d+(?:[._]\d+)?", str(level_key))
        if not match or not isinstance(neighborhoods, dict):
            continue
        level = float(match.group().replace("_", "."))
        for neighborhood, values in neighborhoods.items():
            if not isinstance(values, dict):
                continue
            rows.append({
                "nivel": level,
                "bairro": neighborhood,
                "predios_afetados": values.get("affected_buildings", 0),
                "total_predios": values.get("total_buildings", 0),
                "percentual": values.get("percentage"),
                "populacao": values.get("population", 0),
                "populacao_afetada": values.get("affected_population", 0),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("O JSON não tem níveis e bairros no formato esperado.")
    for col in ["nivel", "predios_afetados", "total_predios", "percentual", "populacao", "populacao_afetada"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    missing_pct = df["percentual"].eq(0) & df["predios_afetados"].gt(0)
    df.loc[missing_pct, "percentual"] = (
        100 * df.loc[missing_pct, "predios_afetados"] / df.loc[missing_pct, "total_predios"].replace(0, pd.NA)
    ).fillna(0)
    return df


def find_local_file(pattern: str) -> Path | None:
    candidates = list(DATA_DIR.glob(pattern)) if DATA_DIR.exists() else []
    candidates += list(ROOT.glob(pattern))
    return candidates[0] if candidates else None


@st.cache_data(show_spinner=False)
def download_file(url: str, filename: str) -> str:
    cache_path = Path(tempfile.gettempdir()) / filename
    if cache_path.exists() and cache_path.stat().st_size > 100_000:
        return str(cache_path)
    response = requests.get(url, headers=HEADERS, timeout=180, stream=True)
    response.raise_for_status()
    temp_path = cache_path.with_suffix(cache_path.suffix + ".part")
    with temp_path.open("wb") as out:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                out.write(chunk)
    temp_path.replace(cache_path)
    return str(cache_path)


@st.cache_data(show_spinner=False)
def get_layers(path: str) -> list[str]:
    return pyogrio.list_layers(path)[:, 0].tolist()


def choose_layer(layers: list[str], patterns: list[str]) -> str | None:
    for pattern in patterns:
        found = next((layer for layer in layers if re.search(pattern, layer, re.I)), None)
        if found:
            return found
    return None


@st.cache_data(show_spinner=False)
def get_city_polygon(city: str) -> gpd.GeoDataFrame:
    boundary = ox.geocode_to_gdf(f"{city}, Rio Grande do Sul, Brasil")
    if boundary.empty:
        raise ValueError(f"Não foi possível obter o limite municipal de {city}.")
    return boundary.to_crs(4326)


@st.cache_data(show_spinner=False)
def get_osm_roads(city: str) -> gpd.GeoDataFrame:
    graph = ox.graph_from_place(f"{city}, Rio Grande do Sul, Brasil", network_type="drive")
    edges = ox.graph_to_gdfs(graph, nodes=False, edges=True).reset_index()
    keep = [col for col in ["highway", "name", "ref", "geometry"] if col in edges.columns]
    edges = edges[keep].to_crs(4326)
    # OSMnx retorna a rede direcionada; remove geometrias idênticas no sentido oposto.
    edges["_geometry_key"] = edges.geometry.map(lambda geometry: geometry.normalize().wkb if geometry is not None else None)
    return edges.drop_duplicates("_geometry_key").drop(columns="_geometry_key")


@st.cache_data(show_spinner=False)
def calculate_city(city: str, flood_path: str, roads_path: str | None) -> dict:
    """Cruza linhas viárias com a mancha observada e soma a extensão sobreposta."""
    city_polygon = get_city_polygon(city)
    flood_layers = get_layers(flood_path)
    flood_layer = choose_layer(flood_layers, [
        r"planet.*skysat.*inundacao.*20240506",
        r"sentinel2.*agua.*20240506.*validada",
        r"sentinel2.*agua.*20240506",
        r"inundacao",
        r"agua",
    ])
    if not flood_layer:
        raise ValueError("Não encontrei uma camada vetorial de água/inundação no GeoPackage.")

    flood = gpd.read_file(flood_path, layer=flood_layer)
    if flood.crs is None:
        raise ValueError("A camada de inundação está sem sistema de coordenadas definido.")
    flood = flood.to_crs(city_polygon.crs)
    flood = gpd.clip(flood, city_polygon)
    flood = flood[flood.geometry.notna() & ~flood.geometry.is_empty]
    if flood.empty:
        return {"city": city, "has_flood": False, "flood_layer": flood_layer}

    roads = gpd.GeoDataFrame()
    road_source = ""
    if roads_path:
        road_layer = choose_layer(get_layers(roads_path), [r"via", r"road", r"line"])
        if road_layer:
            roads = gpd.read_file(roads_path, layer=road_layer)
            if not roads.empty:
                roads = roads.to_crs(city_polygon.crs)
                roads = gpd.clip(roads, city_polygon)
                road_source = "GeoPackage de vias OpenStreetMap (Zenodo)"
    if roads.empty:
        roads = get_osm_roads(city)
        roads = gpd.clip(roads, city_polygon)
        road_source = "OpenStreetMap, consultado via OSMnx"
    if roads.empty:
        raise ValueError(f"Não encontrei vias para cruzar em {city}.")

    type_col = "highway" if "highway" in roads.columns else "fclass" if "fclass" in roads.columns else None
    def translate_road_type(value: object) -> str:
        values = value if isinstance(value, (list, tuple)) else [value]
        translated = [ROAD_LABELS.get(str(item), str(item).replace("_", " ").capitalize()) for item in values]
        return ", ".join(dict.fromkeys(translated))

    def group_road_type(value: object) -> str:
        values = value if isinstance(value, (list, tuple)) else [value]
        groups = [ROAD_GROUPS.get(str(item), "Outras vias") for item in values]
        return ", ".join(dict.fromkeys(groups))

    roads["tipo_via"] = roads[type_col].map(translate_road_type) if type_col else "Via sem classificação"
    roads["grupo_via"] = roads[type_col].map(group_road_type) if type_col else "Outras vias"
    roads_m = roads.to_crs(31982)
    roads_m = roads_m[roads_m.geometry.notna() & ~roads_m.geometry.is_empty].copy()
    roads_m["comprimento_km"] = roads_m.geometry.length / 1000
    water = flood.to_crs(31982).geometry.union_all()
    roads_m["geometria_exposta"] = roads_m.geometry.intersection(water)
    roads_m["km_afetados"] = roads_m["geometria_exposta"].length / 1000
    roads_m["status"] = roads_m["km_afetados"].gt(0).map({True: "Dentro da mancha", False: "Fora da mancha"})
    total_km = float(roads_m["comprimento_km"].sum())
    affected_km = float(roads_m["km_afetados"].sum())
    roads_wgs = roads_m.to_crs(4326)
    return {
        "city": city,
        "has_flood": True,
        "roads": roads_wgs,
        "total_km": total_km,
        "affected_km": affected_km,
        "percent": 100 * affected_km / total_km if total_km else 0,
        "road_source": road_source,
        "flood_layer": flood_layer,
    }

def render_road_map(result: dict, roads: gpd.GeoDataFrame | None = None) -> None:
    roads = roads if roads is not None else result["roads"]
    affected = roads[roads["km_afetados"] > 0]
    if affected.empty:
        st.info("Não há trechos desta seleção dentro da mancha de inundação.")
        return
    st.caption("O mapa mostra somente os trechos dentro da mancha; vias fora dela não são desenhadas.")
    shown = affected
    lats: list[float | None] = []
    lons: list[float | None] = []
    statuses: list[str] = []
    road_types: list[str] = []

    for row in shown.itertuples():
        geometry = row.geometry
        lines = [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms) if geometry.geom_type == "MultiLineString" else []
        for line in lines:
            xs, ys = line.xy
            lons.extend(list(xs) + [None])
            lats.extend(list(ys) + [None])
            statuses.extend([row.status] * (len(xs) + 1))
            road_types.extend([row.tipo_via] * (len(xs) + 1))
    map_df = pd.DataFrame({"lat": lats, "lon": lons, "Situação": statuses, "Classe da via": road_types})
    center = get_city_polygon(result["city"]).geometry.iloc[0].centroid
    fig = px.line_map(
        map_df,
        lat="lat",
        lon="lon",
        color="Situação",
        hover_name="Classe da via",
        color_discrete_map={"Dentro da mancha": "#dc5c51"},
        zoom=10,
        center={"lat": center.y, "lon": center.x},
        height=550,
    )
    # Desenha o contorno municipal completo, incluindo zonas urbanas e rurais.
    boundary = get_city_polygon(result["city"]).geometry.iloc[0]
    polygons = [boundary] if boundary.geom_type == "Polygon" else list(boundary.geoms)
    boundary_lats: list[float | None] = []
    boundary_lons: list[float | None] = []
    for polygon in polygons:
        coords = list(polygon.exterior.coords)
        boundary_lons.extend([point[0] for point in coords] + [None])
        boundary_lats.extend([point[1] for point in coords] + [None])
    fig.add_trace(go.Scattermap(
        lon=boundary_lons,
        lat=boundary_lats,
        mode="lines",
        line={"color": "#f5c542", "width": 4},
        name=f"Limite municipal de {result['city']}",
        hoverinfo="name",
    ))
    fig.update_layout(margin={"l": 0, "r": 0, "t": 10, "b": 0}, showlegend=True, legend_title_text="Mapa", font={"color": "#ffffff"}, legend={"font": {"color": "#ffffff"}, "title_font": {"color": "#ffffff"}, "bgcolor": "rgba(12, 24, 27, 0.82)"})
    st.plotly_chart(fig, width="stretch")


def collection_date() -> str:
    metadata = DATA_DIR / "coleta_info.json"
    if metadata.exists():
        try:
            collected = json.loads(metadata.read_text(encoding="utf-8")).get("coleta_em")
            if collected:
                return datetime.fromisoformat(collected).astimezone().strftime("%d/%m/%Y")
        except (ValueError, OSError):
            pass
    return datetime.now().astimezone().strftime("%d/%m/%Y")


def render_mobility(city: str, show_analytics: bool = False) -> None:
    st.subheader(f"Quilômetros de vias dentro da mancha | {city}")
    flood_local = find_local_file("cheias_rhguaiba_2024_db*.gpkg")
    roads_local = find_local_file("insumos_openstreetmaps_vias*.gpkg")
    try:
        with st.spinner("Carregando bases geográficas e calculando a sobreposição das vias..."):
            flood_path = str(flood_local) if flood_local else download_file(FLOOD_URL, "cheias_rhguaiba_2024_db_v11.gpkg")
            roads_path = str(roads_local) if roads_local else download_file(ROADS_URL, "insumos_openstreetmaps_vias_rhguaiba.gpkg")
            result = calculate_city(city, flood_path, roads_path)
    except Exception as exc:
        st.error(f"Não foi possível calcular os quilômetros de vias para {city}: {exc}")
        st.info("Coloque os GeoPackages da coleta em `dados/originais/` ou execute `python coleta_bases.py` na pasta do projeto. A busca do limite municipal e das vias também precisa de acesso à internet.")
        return
    if not result["has_flood"]:
        st.warning(f"A camada `{result['flood_layer']}` não contém polígonos sobre {city}. O app não estima quilômetros sem uma mancha de inundação observada para essa área.")
        st.caption(f"Camada consultada: {result['flood_layer']} · Base de inundação: GeoPackage Zenodo, observação de 06/05/2024.")
        return

    roads = result["roads"]
    if show_analytics:
        road_groups = sorted(roads["grupo_via"].dropna().unique().tolist())
        chosen_group = st.selectbox("Filtrar tipo de via", ["Todos os tipos", *road_groups], key=f"filtro_tipo_via_{normalize_text(city)}")
        if chosen_group != "Todos os tipos":
            roads = roads[roads["grupo_via"] == chosen_group].copy()
        st.caption("Rodovias e ruas foram agrupadas para facilitar a leitura; ciclovias, caminhos, trilhas e estradas rurais continuam separados.")
    affected_km = float(roads["km_afetados"].sum())
    total_km = float(roads["comprimento_km"].sum())
    pct = 100 * affected_km / total_km if total_km else 0.0
    a, b, c = st.columns(3)
    a.metric("Vias cobertas pela água", f"{br_num(affected_km, 1)} km", help="Soma apenas os pedaços das ruas e estradas que cruzam a mancha de inundação mapeada.")
    b.metric("Parte da rede atingida", f"{br_num(pct, 1)}%", help="Quilômetros dentro da mancha divididos pelo total de quilômetros de vias mapeadas no município.")
    c.metric("Total de vias mapeadas", f"{br_num(total_km, 1)} km", help="Extensão de vias encontrada dentro do limite do município e incluída nesta análise.")
    st.info(f"**Como ler:** de cada {br_num(total_km, 1)} km de vias mapeadas em {city}, cerca de {br_num(affected_km, 1)} km aparecem dentro da mancha de água ({br_num(pct, 1)}%). É a soma dos trechos cobertos, não necessariamente ruas inteiras.")
    if show_analytics:
        map_col, summary_col = st.columns([1.5, 1])
        with map_col:
            st.markdown("#### Mapa de exposição viária")
            render_road_map(result, roads)
        with summary_col:
            st.markdown("#### Vias dentro e fora da mancha")
            outside_km = max(total_km - affected_km, 0.0)
            donut = px.pie(
                pd.DataFrame({"Situação": ["Dentro da mancha", "Fora da mancha"], "km": [affected_km, outside_km]}),
                names="Situação", values="km", hole=.68,
                color="Situação", color_discrete_map={"Dentro da mancha": "#dc5c51", "Fora da mancha": "#087e83"},
            )
            donut.update_layout(template="plotly_white", paper_bgcolor="#f5f8f7", plot_bgcolor="#ffffff", font={"color": "#000000"}, legend={"font": {"color": "#000000"}, "title_font": {"color": "#000000"}}, showlegend=True, legend_title_text="Situação das vias", margin={"l": 0, "r": 0, "t": 8, "b": 8}, height=360)
            donut.update_traces(textfont={"color": "#000000"})
            st.plotly_chart(donut, width="stretch")
        st.markdown("#### Quilômetros atingidos por tipo de via")
        by_type = roads.groupby("grupo_via", as_index=False)["km_afetados"].sum().sort_values("km_afetados", ascending=False)
        chart = px.bar(by_type.sort_values("km_afetados"), x="km_afetados", y="grupo_via", orientation="h", text_auto=".1f", labels={"km_afetados": "Quilômetros cobertos pela água", "grupo_via": "Tipo de via"}, color_discrete_sequence=["#087e83"])
        chart.update_layout(template="plotly_white", paper_bgcolor="#f5f8f7", plot_bgcolor="#ffffff", font={"color": "#000000"}, showlegend=False, margin={"l": 0, "r": 12, "t": 8, "b": 8}, height=430)
        chart.update_traces(texttemplate="%{x:.1f} km", textposition="outside", cliponaxis=False, textfont={"color": "#000000"})
        chart.update_xaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        chart.update_yaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        st.plotly_chart(chart, width="stretch")
    else:
        render_road_map(result, roads)
    source_date = collection_date()
    st.markdown(f"Fontes: [GeoPackage de inundação (Zenodo)](https://zenodo.org/records/12593168), camada `{result['flood_layer']}` (mancha de 06/05/2024); [malha viária do OpenStreetMap](https://www.openstreetmap.org/) ({result['road_source']}). Data da coleta/consulta: **{source_date}**.")
    st.caption("Extensão calculada pela interseção geométrica das linhas com os polígonos de água, em SIRGAS 2000 / UTM 22S.")
    st.markdown('<p class="note">A métrica indica extensão de vias coberta pela mancha mapeada; ela não representa interdições oficiais nem confirma a condição operacional da estrada.</p>', unsafe_allow_html=True)


def page_poa() -> None:
    st.markdown('<div class="hero"><div class="eyebrow">Tela 1 · Porto Alegre</div><h1>Quando a água encontra a cidade</h1><p>Simulação por cota do Guaíba e extensão de vias dentro da mancha observada em maio de 2024.</p></div>', unsafe_allow_html=True)
    try:
        df = read_inct_json()
    except Exception as exc:
        st.error(f"Não consegui ler os dados de simulação: {exc}")
        return
    levels = sorted(df["nivel"].unique())
    slider = st.slider("Cota simulada do Guaíba", float(min(levels)), float(max(levels)), 5.3, 0.1, format="%.1f m")
    chosen = min(levels, key=lambda value: abs(value - slider))
    data = df[df["nivel"].eq(chosen)].copy()
    hit = data[data["predios_afetados"] > 0].sort_values("percentual", ascending=False)
    a, b, c = st.columns(3)
    a.metric("População afetada estimada", br_num(data["populacao_afetada"].sum()))
    b.metric("Prédios afetados estimados", br_num(data["predios_afetados"].sum()))
    c.metric("Bairros com prédios atingidos", f"{int(data['predios_afetados'].gt(0).sum())} / {len(data)}")
    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("#### Prédios afetados por bairro")
        fig_bar = px.bar(
            hit.sort_values("percentual"), x="percentual", y="bairro", orientation="h",
            color="percentual", color_continuous_scale=[[0, "#b9e1dc"], [1, "#087e83"]],
            labels={"percentual": "Prédios afetados (%)", "bairro": "Bairro"},
        )
        fig_bar.update_layout(coloraxis_showscale=False, margin={"l": 0, "r": 12, "t": 8, "b": 8}, height=max(520, 24 * len(hit)))
        fig_bar.update_layout(font={"color": "#000000"}, paper_bgcolor="#EBEBEB", plot_bgcolor="#EBEBEB")
        fig_bar.update_xaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        fig_bar.update_yaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        st.plotly_chart(fig_bar, width="stretch")
    with right:
        st.markdown("#### Evolução da população estimada")
        curve = df.groupby("nivel", as_index=False)["populacao_afetada"].sum()
        fig_line = px.area(curve, x="nivel", y="populacao_afetada", labels={"nivel": "Cota (m)", "populacao_afetada": "Pessoas"})
        fig_line.update_traces(line_color="#087e83", fillcolor="rgba(8,126,131,.16)")
        fig_line.add_vline(x=5.35, line_dash="dash", line_color="#dc5c51", annotation_text="5,35 m · maio/2024")
        fig_line.add_vline(x=chosen, line_dash="dot", line_color="#e6a847")
        fig_line.update_layout(margin={"l": 0, "r": 12, "t": 8, "b": 8}, height=435)
        fig_line.update_layout(font={"color": "#000000"}, paper_bgcolor="#EBEBEB", plot_bgcolor="#EBEBEB")
        fig_line.update_xaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        fig_line.update_yaxes(tickfont={"color": "#000000"}, title_font={"color": "#000000"}, color="#000000")
        st.plotly_chart(fig_line, width="stretch")
    with st.expander(f"Ver ranking de bairros na cota {br_num(chosen, 1)} m"):
        columns = ["bairro", "predios_afetados", "total_predios", "percentual", "populacao_afetada"]
        ranking = hit[columns].rename(columns={
            "bairro": "Bairro", "predios_afetados": "Prédios atingidos (estimativa)", "total_predios": "Prédios no bairro",
            "percentual": "Prédios afetados (%)", "populacao_afetada": "População estimada afetada",
        })
        ranking["Margem de erro"] = "Não informada pela fonte"
        st.dataframe(ranking, hide_index=True, width="stretch")
        st.caption("O JSON não fornece intervalo de confiança nem margem de erro numérica. Por isso, os valores são apresentados como estimativas, sem uma faixa de erro inventada.")
    st.markdown('<p class="note">Os valores por bairro são estimativas da simulação do INCT SiMAI, não previsões nem contagens oficiais de campo. A população afetada presume distribuição uniforme entre todos os prédios, inclusive os não residenciais. O arquivo recebido também contém quedas não monotônicas identificadas na auditoria (12 ocorrências em cinco bairros); elas são mantidas como recebidas e precisam ser explicadas no relatório. A tela de vias usa outra base: a mancha de água observada por satélite, cruzada com linhas viárias.</p>', unsafe_allow_html=True)
    json_date = datetime.fromtimestamp(INCT_JSON.stat().st_mtime).astimezone().strftime("%d/%m/%Y")
    st.markdown(f"Fonte da simulação: [INCT SiMAI — Plataforma Flood](https://inct-simai.com.br/?page=home) · JSON fornecido pela equipe · Arquivo recebido em **{json_date}**.")
    st.divider()
    render_mobility("Porto Alegre", show_analytics=True)


def page_taquara() -> None:
    st.markdown('<div class="hero"><div class="eyebrow">Tela 2 · Taquara</div><h1>Acesso e mobilidade sob risco</h1><p>Extensão da rede viária inserida na mancha de inundação mapeada em maio de 2024.</p></div>', unsafe_allow_html=True)
    render_mobility("Taquara", show_analytics=True)


with st.sidebar:
    st.markdown("## Enchentes - RS  ⛈️🫯")
    st.caption("Mobilidade e impacto territorial · 2024")
    screen = st.radio("Município", ["Porto Alegre", "Taquara"], index=0)
    st.divider()
    st.caption("Use a navegação para comparar a simulação urbana de Porto Alegre e a exposição observada da malha viária nos dois municípios.")

if screen == "Porto Alegre":
    page_poa()
else:
    page_taquara()
