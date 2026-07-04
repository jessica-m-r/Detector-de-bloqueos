import time
from icrawler.builtin import BingImageCrawler

terminos = [
    "bloqueo calles protesta",
    "manifestación multitud",
    "protestas en la calle",
    "street protest blockade",
    "gente bloqueando calles",
    "protesta vía pública",
    "bloqueo manifestantes",
]

for termino in terminos:
    print(f"\n Descargando: {termino}")
    crawler = BingImageCrawler(storage={"root_dir": f"imagenes_dataset/{termino}"})
    crawler.crawl(keyword=termino, max_num=10, min_size=(800, 800))
    print(f" Descargadas para: {termino}")
    time.sleep(5)  