import os
import glob
import rasterio
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np

# Caminhos das pastas
pasta_geral = 'C:/IMAGENS/'
pasta_1_bandas = pasta_geral + '1_bandas/'
pasta_3_imagens_rgb = pasta_geral + '3_imagens_rgb/'
pasta_6_ndvi = pasta_geral + '6_ndvi_4326/'
pasta_temp_reprojetadas = pasta_geral + 'temp_reprojetadas/'  # Pasta temporária para arquivos reprojetados

# Criar pasta temporária se não existir
os.makedirs(pasta_temp_reprojetadas, exist_ok=True)

# Reprojetar imagens para EPSG:32722 (22S)
def reprojetar_imagem(input_path, output_path, crs_destino="EPSG:32722"):
    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, crs_destino, src.width, src.height, *src.bounds)
        perfil = src.profile.copy()
        perfil.update({
            'crs': crs_destino,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(output_path, 'w', **perfil) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=crs_destino,
                    resampling=Resampling.nearest
                )

# Listar arquivos de banda
arquivos_band2 = sorted(glob.glob(pasta_1_bandas + '*_B2.TIF'))
arquivos_band3 = sorted(glob.glob(pasta_1_bandas + '*_B3.TIF'))
arquivos_band4 = sorted(glob.glob(pasta_1_bandas + '*_B4.TIF'))
arquivos_band5 = sorted(glob.glob(pasta_1_bandas + '*_B5.TIF'))  # Infravermelho

if not (arquivos_band2 and arquivos_band3 and arquivos_band4 and arquivos_band5):
    print("As bandas necessárias (B2, B3, B4, B5) não foram encontradas.")
    exit()

# Reprojetar todas as bandas para a pasta temporária
arquivos_reprojetados = {"B2": [], "B3": [], "B4": [], "B5": []}
for b2, b3, b4, b5 in zip(arquivos_band2, arquivos_band3, arquivos_band4, arquivos_band5):
    try:
        nome_base = os.path.basename(b2).split('_B2.TIF')[0]

        # Reprojetar cada banda
        b2_reproj = f"{pasta_temp_reprojetadas}{nome_base}_B2_REPROJ.TIF"
        b3_reproj = f"{pasta_temp_reprojetadas}{nome_base}_B3_REPROJ.TIF"
        b4_reproj = f"{pasta_temp_reprojetadas}{nome_base}_B4_REPROJ.TIF"
        b5_reproj = f"{pasta_temp_reprojetadas}{nome_base}_B5_REPROJ.TIF"

        reprojetar_imagem(b2, b2_reproj)
        reprojetar_imagem(b3, b3_reproj)
        reprojetar_imagem(b4, b4_reproj)
        reprojetar_imagem(b5, b5_reproj)

        arquivos_reprojetados["B2"].append(b2_reproj)
        arquivos_reprojetados["B3"].append(b3_reproj)
        arquivos_reprojetados["B4"].append(b4_reproj)
        arquivos_reprojetados["B5"].append(b5_reproj)

        print(f"B2, B3, B4 e B5 reprojetadas para {nome_base}")
    except Exception as e:
        print(f"Erro ao reprojetar as bandas para {b2}, {b3}, {b4}, {b5}: {e}")
        exit()

# Criar imagens RGBI
arquivos_rgbi = []
for b2, b3, b4, b5 in zip(arquivos_reprojetados["B2"], arquivos_reprojetados["B3"], arquivos_reprojetados["B4"], arquivos_reprojetados["B5"]):
    try:
        with rasterio.open(b2) as band2, rasterio.open(b3) as band3, rasterio.open(b4) as band4, rasterio.open(b5) as band5:
            # Ler bandas
            b2_data = band2.read(1)
            b3_data = band3.read(1)
            b4_data = band4.read(1)
            b5_data = band5.read(1)

            perfil = band2.profile
            perfil.update(count=4)  # Multibanda (RGBI)

            # Criar arquivo RGBI
            nome_rgbi = pasta_3_imagens_rgb + os.path.basename(b2).replace('_B2_REPROJ.TIF', '_RGBI.TIF')
            with rasterio.open(nome_rgbi, 'w', **perfil) as rgbi:
                rgbi.write(b4_data, 1)  # Vermelho
                rgbi.write(b3_data, 2)  # Verde
                rgbi.write(b2_data, 3)  # Azul
                rgbi.write(b5_data, 4)  # Infravermelho

            arquivos_rgbi.append(nome_rgbi)
            print(f"Imagem RGBI criada e salva em {nome_rgbi}")
    except Exception as e:
        print(f"Erro ao criar imagem RGBI para {b2}, {b3}, {b4}, {b5}: {e}")
        exit()

# Criar mosaico
try:
    src_files_to_mosaic = [rasterio.open(f) for f in arquivos_rgbi]
    mosaic, out_trans = merge(src_files_to_mosaic)

    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "crs": "EPSG:32722"
    })

    mosaic_file = pasta_3_imagens_rgb + "RGB_"+nome_base+".tif"
    with rasterio.open(mosaic_file, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"Mosaico RGBI salvo em {mosaic_file}")
except Exception as e:
    print(f"Erro ao criar o mosaico: {e}")
    exit()

# Calcular NDVI
try:
    with rasterio.open(mosaic_file) as src:
        band_red = src.read(1).astype(float)  # Vermelho
        band_nir = src.read(4).astype(float)  # Infravermelho próximo

        # Calcular NDVI
        np.seterr(invalid='ignore')
        ndvi = (band_nir - band_red) / (band_nir + band_red)
        ndvi[np.isnan(ndvi)] = -9999
        ndvi = np.clip(ndvi, -1, 1)

        profile = src.profile
        profile.update(dtype=rasterio.float32, count=1, nodata=-9999)

        ndvi_file = pasta_6_ndvi + "NDVI_RGB_"+nome_base+".tif"
        with rasterio.open(ndvi_file, 'w', **profile) as dst:
            dst.write(ndvi.astype(rasterio.float32), 1)

        print(f"NDVI salvo em {ndvi_file}")
except Exception as e:
    print(f"Erro ao calcular o NDVI: {e}")
