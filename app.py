import streamlit as st
import folium
import geopandas as gpd
from folium.plugins import MarkerCluster, HeatMap, MeasureControl
import branca.colormap as cm
import requests
from io import BytesIO
import json
from streamlit_folium import st_folium  # Importação essencial

# Configuração da página
st.set_page_config(
    page_title="Mapa de Sistemas Bancários",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Mapa de Sistemas Bancários por Bairro")
st.markdown("Visualização interativa de dados geográficos carregados do GitHub")

# URLs dos dados hospedados no GitHub
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Analissoares/meu-repositorio/main/"
BAIRROS_URL = GITHUB_RAW_URL + "dados/bairros.geojson"
SB_URL = GITHUB_RAW_URL + "dados/dados_SB.geojson"

@st.cache_data(ttl=3600)
def load_geojson_from_github(url):
    """Carrega um arquivo GeoJSON do GitHub"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Carrega o GeoJSON diretamente da resposta como BytesIO
        return gpd.read_file(BytesIO(response.content))
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {str(e)}")
        st.error(f"URL tentada: {url}")
        return None

# Carregando os dados
with st.spinner('🔄 Carregando dados do GitHub...'):
    bairros_data = load_geojson_from_github(BAIRROS_URL)
    df_sb = load_geojson_from_github(SB_URL)

# Verifica se os dados carregaram corretamente
if bairros_data is None:
    st.stop()
if df_sb is None:
    st.stop()

# Processamento dos dados
with st.spinner('⚙️ Processando dados...'):
    bairros_data = bairros_data.to_crs(epsg=4326)
    df_sb = df_sb.to_crs(epsg=4326)

    # Spatial join + contagem de pontos por bairro
    join = gpd.sjoin(bairros_data, df_sb, how="left", predicate="contains")
    counts = join.groupby(join.index).size()
    bairros_data["sistemas_bancarios"] = counts.reindex(bairros_data.index, fill_value=0)

# Interface do usuário
with st.sidebar:
    st.header("Configurações do Mapa")
    tile_layer = st.selectbox(
        "Estilo do Mapa Base",
        ["OpenStreetMap", "CartoDB positron", "Stamen Terrain"],
        index=0
    )
    show_heatmap = st.checkbox("Mostrar mapa de calor", True)
    show_clusters = st.checkbox("Mostrar agrupamento de marcadores", True)

# Criação do mapa
m = folium.Map(location=[-25.5, -49.3], tiles=tile_layer, zoom_start=12)

# Colormap
min_val = bairros_data["sistemas_bancarios"].min()
max_val = bairros_data["sistemas_bancarios"].max()
colormap = cm.LinearColormap(
    colors=['#fef9ef', '#f3d9b1', '#d8b07a'],
    vmin=min_val,
    vmax=max_val,
    caption='Quantidade de Sistemas Bancários'
)

# Estilo dos bairros
def style_function(feature):
    value = feature['properties'].get('sistemas_bancarios', 0)
    return {
        'fillColor': colormap(value),
        'color': 'black',
        'weight': 1.5,
        'fillOpacity': 0.7,
    }

# Adiciona bairros ao mapa
folium.GeoJson(
    bairros_data,
    name="Sistemas Bancários por Bairro",
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=["NOME", "sistemas_bancarios"],
        aliases=["Bairro:", "Qtd. de Sistemas Bancários:"],
        localize=True,
        sticky=False,
        labels=True,
        style="""
            background-color: white;
            color: black;
            font-family: arial;
            font-size: 12px;
            padding: 5px;
        """
    )
).add_to(m)

# Adiciona marcadores
locations = [
    [geom.y, geom.x]
    for geom in df_sb.geometry
    if geom and geom.geom_type == 'Point' and not geom.is_empty
]

if show_clusters:
    marker_cluster = MarkerCluster(name='Sistemas Bancários (pontos)')
    for loc in locations:
        folium.Marker(location=loc).add_to(marker_cluster)
    marker_cluster.add_to(m)

if show_heatmap and locations:
    HeatMap(locations, name='Mapa de Calor').add_to(m)

# Adiciona controle
colormap.add_to(m)
folium.LayerControl().add_to(m)
m.add_child(MeasureControl())

# Exibe o mapa
st_data = st_folium(m, width=1200, height=700)

# Informações adicionais
st.markdown("---")
st.markdown("""
### ℹ️ Sobre os dados:
- **Bairros**: Dados geográficos dos bairros.
- **Sistemas Bancários**: Localização de agências bancárias.
- **Fonte**: Dados carregados diretamente do GitHub.
""")

# Botão para baixar CSV
@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

csv = convert_df(bairros_data[['NOME', 'sistemas_bancarios']])
st.download_button(
    label="⬇️ Baixar dados processados (CSV)",
    data=csv,
    file_name='sistemas_bancarios_por_bairro.csv',
    mime='text/csv',
)


