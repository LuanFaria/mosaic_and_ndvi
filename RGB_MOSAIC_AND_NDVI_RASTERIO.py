#tirar as nuvens das imagens, mosaicos, gerar RGB e NDVI

import os
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
import glob
import numpy as np


pasta_geral='C:/IMAGENS/'
pasta_1_bandas_brutas = pasta_geral + '1_bandas/'
pasta_3_mosaico = pasta_geral + '7_mosaic_4326/'
pasta_4_rgb = pasta_geral + '3_imagens_rgb/'
pasta_6_ndvi = pasta_geral + '6_ndvi_4326/'

lista_unicos = []
for file in os.listdir(pasta_1_bandas_brutas):
    count = 0 
    for caractere in file:
        count = count + 1
    if count > 40:
        lista_unicos.append(file[139:-4])
    else:
        lista_unicos.append(file[7:-4]) 

lista_unicos = (set(lista_unicos))
for unique in lista_unicos:
    search_criteria = "*"+unique+".jp2"
    selecao = os.path.join(pasta_1_bandas_brutas, search_criteria)
    bandsJp2 = glob.glob(selecao)

    src_files_to_mosaic = []
    
    for band in bandsJp2:
            src = rasterio.open(band)
            src_files_to_mosaic.append(src)

    #print(src_files_to_mosaic)
        
    mosaic, out_trans = merge(src_files_to_mosaic)
    
    out_meta = src.meta.copy()
    out_meta.update({"driver": "JP2OpenJPEG",
                     "height": mosaic.shape[1],
                     "width": mosaic.shape[2],
                     "transform": out_trans,
                     "crs": "EPSG:32722" #herdar das imagens "EPSG:32722"
                     }
                    )

    if band[34:38] == 'S2B_':
        with rasterio.open(pasta_3_mosaico+band[34:38]+unique+".jp2", "w", **out_meta) as dest:
             dest.write(mosaic)
    else:
        with rasterio.open(pasta_3_mosaico+'S2A_'+unique+".jp2", "w", **out_meta) as dest:
             dest.write(mosaic)

print('\nGerando RGB')    
lista_bandas = []
for file in os.listdir(pasta_3_mosaico):
    lista_bandas.append(file[:19])

lista_bandas = (set(lista_bandas))
for unique in lista_bandas:        
    #gerar RGB
        b4 = rasterio.open(pasta_3_mosaico+unique+'_B04.jp2')
        b3 = rasterio.open(pasta_3_mosaico+unique+'_B03.jp2')
        b2 = rasterio.open(pasta_3_mosaico+unique+'_B02.jp2')
        b8 = rasterio.open(pasta_3_mosaico+unique+'_B08.jp2')


        #Create an RGB image 
        with rasterio.open(pasta_4_rgb+'RGB_'+unique+'_4328.tif','w',driver='GTiff', width=b4.width, height=b4.height, 
                count=4,crs=b4.crs,transform=b4.transform, dtype=b4.dtypes[0]) as rgb:
                rgb.write(b4.read(1),1)
                rgb.write(b3.read(1),2)
                rgb.write(b2.read(1),3)
                rgb.write(b8.read(1),4)

        #gerar NDVI
        print('\nGerando NDVI')

        with rasterio.open(pasta_3_mosaico+unique+'_B08.jp2') as srcA:
            bandNir = srcA.read()
            profile = srcA.profile

        with rasterio.open(pasta_3_mosaico+unique+'_B04.jp2') as srcB:     
            bandRed = srcB.read()

        np.seterr(invalid='ignore') #ignora aviso: invalid value encountered in true_divide
        ndvi =(bandNir.astype(float)-bandRed.astype(float))/(bandNir+bandRed)

        profile = srcA.meta
        profile.update(driver='GTiff')
        profile.update(dtype=rasterio.float32)

        result = pasta_6_ndvi+'NDVI_RGB_'+unique+'_4328.tif'
        with rasterio.open(result, 'w', **profile) as dst:
            dst.write(ndvi.astype(rasterio.float32))
            crs = srcA.crs
