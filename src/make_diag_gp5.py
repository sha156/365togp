# -*- coding: utf-8 -*-
"""生成一组最小编码诊断 .gp5 文件，一次定位目标软件的 GP5 字符串解码方式。

用法: python src/make_diag_gp5.py            # 输出到 output/diag/
判定: 在你实际使用的软件里依次打开 4 个文件，看哪个文件的 marker 中文/重音正常。

  A_ascii.gp5   纯 ASCII 对照 —— 任何软件都应正常；若 A 也乱，问题不在编码
  B_gbk.gp5     GBK(cp936) 字节 —— 正常 => 该软件按 GBK/系统ANSI 解码
  C_utf8.gp5    UTF-8 字节     —— 正常 => 该软件按 UTF-8 解码
  D_cp1252.gp5  cp1252 西欧重音 —— 只有 D 正常 => 该软件固定 cp1252 解码
"""
import pathlib

import guitarpro as gp

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "output" / "diag"

# 每个文件: (文件名, 写入编码, marker 文本, 曲名)
# marker 前缀用 ASCII 标注文件身份，乱码时也能认出是哪个文件
CASES = [
    ("A_ascii.gp5", "ascii",
     "A-ASCII: plain marker bpm=100", "DIAG A ascii"),
    ("B_gbk.gp5", "cp936",
     "B-GBK: 每日必弹②→Ｇ（测试） bpm=100", "DIAG B gbk"),
    ("C_utf8.gp5", "utf-8",
     "C-UTF8: 每日必弹②→Ｇ（测试） bpm=100", "DIAG C utf8"),
    ("D_cp1252.gp5", "cp1252",
     "D-CP1252: Café déjà vu élan bpm=100", "DIAG D cp1252"),
]


def make_song(title: str, marker_text: str) -> gp.Song:
    song = gp.Song()
    song.title = title
    song.tempo = 100
    track = song.tracks[0]
    track.name = "Diag Guitar"
    header = song.measureHeaders[0]
    header.marker = gp.Marker(title=marker_text)
    voice = track.measures[0].voices[0]
    for fret in (0, 2, 3, 2):  # 4 个四分音符，保证可播放
        beat = gp.Beat(voice)
        beat.duration = gp.Duration(value=4)
        beat.text = marker_text[:10]  # beat.text 同样参与编码诊断
        beat.notes.append(gp.Note(beat, value=fret, string=6))
        voice.beats.append(beat)
    return song


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, encoding, marker_text, title in CASES:
        path = OUT_DIR / filename
        gp.write(make_song(title, marker_text), str(path), encoding=encoding)
        print(f"已写入 {path}  (encoding={encoding})")
    print("\n打开 4 个文件各看一眼 marker，对照 docs 判定表即可定位解码方式。")


if __name__ == "__main__":
    main()
