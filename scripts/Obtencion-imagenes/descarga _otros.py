from icrawler.builtin import BingImageCrawler
import time

terminos_otros = [
    "gato mascota", "perro doméstico", "mesa comedor interior",
    "sala de estar", "oficina escritorio", "comida plato",
    "persona retrato interior", "naturaleza bosque", "animal salvaje",
    "objeto random", "ropa tienda", "libro biblioteca",
    "playa mar", "montaña paisaje", "cocina interior",
    "flores jardín", "carro interior asiento", "computadora laptop",
    "fiesta cumpleaños", "deporte gimnasio",
]

for termino in terminos_otros:
    print(f"Descargando: {termino}")
    crawler = BingImageCrawler(storage={"root_dir": f"imagenes_otros/{termino}"})
    crawler.crawl(keyword=termino, max_num=150, min_size=(400, 400))
    time.sleep(3)