"""Memoria de traducción: diccionario original -> traducción, en un JSON reanudable."""
import json
import os


class Memory:
    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.data = json.load(fh)

    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.data[key]

    def __len__(self):
        return len(self.data)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        """Guardado atómico: nunca deja el archivo a medias."""
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=0)
        os.replace(tmp, self.path)
