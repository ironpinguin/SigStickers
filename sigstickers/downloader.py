"""Sticker download and convert functions used by the module entry point."""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

from emoji import demojize
from PIL import Image
from signalstickers_client import StickersClient
from signalstickers_client.models.sticker import Sticker

from .caching import createConverted, verifyConverted

opj = os.path.join


def assureDirExists(directory: str, root: str) -> str:
	"""Make the dir if not exists

	Args:
		directory (str): the directory name
		root (str): the path of the root directory

	Returns:
		str: the full path
	"""
	fullPath = opj(root, directory)
	os.makedirs(fullPath, exist_ok=True)

	return fullPath


def saveSticker(sticker: Sticker, path: str) -> str:
	"""Save a sticker

	Args:
		sticker (Sticker): the sticker object
		path (str): the path to write to
	Returns:
		str: the filepath the file was written to
	"""
	stickeremoji = cast(str, sticker.emoji)
	filePath = opj(
		path,
		f"{sticker.id}+{demojize(stickeremoji)[1:-1]}+{stickeremoji}.webp",
	)
	with open(filePath, "wb") as file:
		file.write(cast(bytes, sticker.image_data))
	return filePath


async def downloadPack(
	packId: str, packKey: str, cwd: str = os.getcwd()
) -> tuple[str, str]:
	"""Download a sticker pack.

	Args:
		packId (str): pack_id from url param. eg b676ec334ee2f771cadff5d095971e8c
		packKey (str): pack_key from url param. eg
		c957a57000626a2dc3cb69bf0e79c91c6b196b74d4d6ca1cbb830d3ad0ad4e36
		cwd (str, optional): set the current working directory

	Returns:
		tuple[str, str]: sticker working directory and pack title
	"""
	print("=" * 60)
	start = time.time()
	async with StickersClient() as client:
		pack = await client.get_pack(packId, packKey)
		packName = cast(str, pack.title)
		end = time.time()
		print(f'Starting to scrape "{packName}" ...')
		print(f"Time taken to scrape {pack.nb_stickers} stickers - {end - start:.3f}s")
		print()

	swd = assureDirExists(packName, root=assureDirExists("downloads", root=cwd))
	webpDir = assureDirExists("webp", root=swd)

	# Save the stickers
	print("-" * 60)
	print(f'Starting download of "{packName}" into {swd}')
	with ThreadPoolExecutor(max_workers=4) as executor:
		for i in as_completed(
			[
				executor.submit(saveSticker, sticker, webpDir)
				for sticker in pack.stickers
			]
		):
			i.result()

	return swd, packName


def convertWithPIL(inputFile: str) -> str:
	"""Convert the webp file to png

	Args:
		inputFile (str): path to input file

	Returns:
		str: path to input file
	"""
	img = Image.open(inputFile)
	img.save(inputFile.replace("webp", "png"))

	try:
		img.save(
			inputFile.replace("webp", "gif"),
			version="GIF89a",
			disposal=2,
			save_all=True,
			loop=0,
		)
	except ValueError:
		print(f"Failed to save {inputFile} as gif")
	return inputFile


async def convertPack(swd: str, packName: str, noCache=False):
	"""Convert the webp images into png and gif images

	Args:
		swd (str): name of the directory to convert
		packName (str): name of the sticker pack (for cache + logging)
		noCache (bool, optional): set to true to disable cache. Defaults to False.
	"""
	print("-" * 60)
	if not noCache and verifyConverted(packName):
		return
	webpDir = assureDirExists("webp", root=swd)
	assureDirExists("png", root=swd)
	assureDirExists("gif", root=swd)

	# Convert stickers
	start = time.time()
	print(f'Converting stickers "{packName}"...')
	converted = 0
	stickers = [opj(webpDir, i) for i in os.listdir(webpDir)]
	total = len(stickers)
	with ThreadPoolExecutor(max_workers=4) as executor:
		for _ in as_completed(
			[executor.submit(convertWithPIL, sticker) for sticker in stickers]
		):
			converted += 1
	end = time.time()
	print(f"Time taken to convert {converted}/{total} stickers - {end - start:.3f}s")

	print()
	createConverted(
		packName,
		data={
			"version": 1,
			"info": {
				"packName": packName,
				"swd": swd,
			},
			"converted": {
				"converted": converted,
				"total": total,
			},
		},
	)
