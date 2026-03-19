#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import sys
import json
import requests
import argparse
import tempfile
import shutil
from urllib.parse import urlparse

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        DownloadColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
except ImportError:
    print("请安装 rich 库: pip install rich")
    sys.exit(1)

# For FLAC conversion
try:
    from pydub import AudioSegment

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3, APIC, TXXX
    from mutagen import File as MutagenFile

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

DEFAULT_DOWNLOAD_PATH = "downloads"

console = Console()


def get_album_detail(album_id: str) -> dict:
    """获取专辑详情"""
    url = f"https://monster-siren.hypergryph.com/api/album/{album_id}/detail"
    response = requests.get(url)
    data = json.loads(response.content)
    return data.get("data", {})


def get_song_info(song_cid: str) -> dict:
    """获取歌曲信息"""
    url = f"https://monster-siren.hypergryph.com/api/song/{song_cid}"
    response = requests.get(url)
    data = json.loads(response.content)
    return data.get("data", {})


def download_file(url: str, file_path: str):
    """下载文件（无进度条，用于歌词和封面）"""
    if not url:
        return

    try:
        response = requests.get(url, stream=True)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except:
        pass


def convert_to_flac(
    audio_path: str,
    cover_path: str = None,
    lyric_path: str = None,
    title: str = None,
    artist: str = None,
    album: str = None,
) -> bool:
    """使用ffmpeg转换音频，mutagen嵌入封面和歌词"""
    if not MUTAGEN_AVAILABLE:
        return False

    try:
        import ffmpeg

        # 检查源文件格式（已在调用处检查）
        temp_dir = tempfile.mkdtemp()
        temp_flac = os.path.join(temp_dir, "output.flac")

        # 使用ffmpeg-python转换音频（不包含封面）
        stream = ffmpeg.input(audio_path)
        ffmpeg.output(
            stream.audio, temp_flac, acodec="flac", ar=44100, ac=2
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)

        # 使用mutagen嵌入封面和歌词
        flac_file = FLAC(temp_flac)

        if title:
            flac_file["TITLE"] = title
        if artist:
            flac_file["ARTIST"] = artist
        if album:
            flac_file["ALBUM"] = album

        if cover_path and os.path.exists(cover_path):
            try:
                from mutagen.flac import Picture

                with open(cover_path, "rb") as f:
                    cover_data = f.read()
                picture = Picture()
                picture.data = cover_data
                picture.type = 3
                picture.mime = (
                    "image/jpeg"
                    if not cover_path.lower().endswith(".png")
                    else "image/png"
                )
                picture.desc = "Cover"
                flac_file.add_picture(picture)
            except Exception as e:
                print(f"嵌入封面失败: {e}")

        if lyric_path and os.path.exists(lyric_path):
            try:
                with open(lyric_path, "r", encoding="utf-8") as f:
                    lyrics = f.read()
                flac_file["LYRICS"] = lyrics
            except Exception as e:
                print(f"嵌入歌词失败: {e}")

        flac_file.save()
        shutil.move(temp_flac, audio_path)
        shutil.rmtree(temp_dir)

        return True
    except Exception as e:
        print(f"转换失败: {e}")
        return False


def download_album(album_id: str, download_path: str = None, to_flac: bool = False):
    """下载专辑（顺序下载）"""
    if download_path is None:
        download_path = DEFAULT_DOWNLOAD_PATH

    console.print(f"[bold]获取专辑 {album_id} 信息...[/bold]")
    album_detail = get_album_detail(album_id)

    album_name = album_detail.get("name", album_id)
    songs = album_detail.get("songs", [])
    cover_url = album_detail.get("coverUrl")
    intro = album_detail.get("intro", "")

    if not songs:
        console.print("[red]未找到歌曲[/red]")
        return

    # 创建专辑文件夹
    album_folder = os.path.join(download_path, album_name)
    os.makedirs(album_folder, exist_ok=True)

    console.print(f"[green]专辑: {album_name}[/green]")
    console.print(f"[green]共 {len(songs)} 首歌曲[/green]\n")
    console.print(f"[blue]保存到: {album_folder}[/blue]\n")

    # 先在后台下载封面和简介（不显示进度）
    if cover_url:
        cover_path = os.path.join(album_folder, "cover.jpg")
        download_file(cover_url, cover_path)

    if intro:
        intro_path = os.path.join(album_folder, "info.txt")
        try:
            with open(intro_path, "w", encoding="utf-8") as f:
                f.write(intro)
        except:
            pass

    # 顺序下载每首歌曲
    success_count = 0
    failed_count = 0

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        DownloadColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for i, song in enumerate(songs, 1):
            song_cid = song.get("cid")
            name = song.get("name")

            if not song_cid:
                continue

            try:
                # 获取歌曲信息
                song_info = get_song_info(song_cid)

                if not song_info:
                    progress.console.print(f"[red]无法获取歌曲信息: {name}[/red]")
                    failed_count += 1
                    continue

                source_url = song_info.get("sourceUrl")

                if not source_url:
                    progress.console.print(f"[red]无法获取下载链接: {name}[/red]")
                    failed_count += 1
                    continue

                # 下载歌曲（带进度条）
                parsed = urlparse(source_url)
                ext = os.path.splitext(parsed.path)[1].split("?")[0]
                if not ext:
                    ext = ".wav"
                file_path = os.path.join(album_folder, f"{name}{ext}")

                task_id = progress.add_task(
                    f"[{i}/{len(songs)}] {name[:20]}...", total=100
                )

                response = requests.get(source_url, stream=True)
                total_size = int(response.headers.get("content-length", 0))

                if total_size > 0:
                    progress.update(task_id, total=total_size)

                downloaded = 0
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress.update(task_id, completed=downloaded)

                # 确保完成显示
                if total_size > 0:
                    progress.update(task_id, completed=total_size, total=total_size)
                else:
                    progress.update(task_id, completed=100, total=100)

                # 如果需要转换为FLAC
                if to_flac:
                    # 检查文件格式
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext == ".mp3":
                        pass
                    else:
                        cover_path = os.path.join(album_folder, "cover.jpg")
                        lyric_url = song_info.get("lyricUrl")
                        lyric_path = (
                            os.path.join(album_folder, f"{name}.lrc")
                            if lyric_url
                            else None
                        )
                        if lyric_url:
                            download_file(lyric_url, lyric_path)
                        artists = song_info.get("artists", [])
                        artist_name = ", ".join(artists) if artists else album_name
                        if convert_to_flac(
                            file_path,
                            cover_path,
                            lyric_path,
                            name,
                            artist_name,
                            album_name,
                        ):
                            # 转换后修改扩展名
                            new_path = os.path.join(album_folder, f"{name}.flac")
                            if os.path.exists(new_path):
                                os.remove(new_path)
                            os.rename(file_path, new_path)
                            file_path = new_path

                # 下载歌词（非FLAC模式下下载歌词）
                if not to_flac:
                    lyric_url = song_info.get("lyricUrl")
                    if lyric_url:
                        lyric_path = os.path.join(album_folder, f"{name}.lrc")
                        download_file(lyric_url, lyric_path)

                success_count += 1

            except Exception as e:
                progress.console.print(f"[red]失败: {name} - {e}[/red]")
                failed_count += 1

    console.print(f"\n[bold green]========== 下载完成 ==========[/bold green]")
    console.print(f"[green]成功: {success_count}/{len(songs)}[/green]")
    if failed_count > 0:
        console.print(f"[red]失败: {failed_count}[/red]")
    console.print(f"[blue]保存位置: {os.path.abspath(download_path)}[/blue]")


def search_albums(keyword: str) -> list:
    """搜索专辑"""
    url = "https://monster-siren.hypergryph.com/api/albums"
    response = requests.get(url)
    data = json.loads(response.content)
    albums = data.get("data", [])

    if keyword:
        return [a for a in albums if keyword.lower() in a.get("name", "").lower()]
    return albums


def list_albums() -> list:
    """获取专辑列表"""
    url = "https://monster-siren.hypergryph.com/api/albums"
    response = requests.get(url)
    data = json.loads(response.content)
    return data.get("data", [])


def main():
    parser = argparse.ArgumentParser(
        description="MSRDesktop CLI - 明日方舟音乐下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  列出所有专辑:
    python msr_cli.py list
  
  搜索专辑:
    python msr_cli.py search "春弦"
  
  下载专辑:
    python msr_cli.py album --id 6678
  
  下载专辑到指定目录:
    python msr_cli.py album --id 6678 --path ./music
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    subparsers.add_parser("list", help="列出所有专辑")

    all_parser = subparsers.add_parser("all", help="下载所有专辑")
    all_parser.add_argument(
        "--path", type=str, default=DEFAULT_DOWNLOAD_PATH, help="下载目录"
    )
    all_parser.add_argument("--flac", action="store_true", help="转换为FLAC格式")

    search_parser = subparsers.add_parser("search", help="搜索专辑")
    search_parser.add_argument("keyword", type=str, help="搜索关键词")

    album_parser = subparsers.add_parser("album", help="下载专辑")
    album_parser.add_argument("--id", type=str, help="专辑ID")
    album_parser.add_argument(
        "--path", type=str, default=DEFAULT_DOWNLOAD_PATH, help="下载目录"
    )
    album_parser.add_argument(
        "--flac", action="store_true", help="转换为FLAC格式并封入封面和歌词"
    )
    album_parser.add_argument("--ids", type=str, help="批量下载，多个ID用逗号分隔")
    album_parser.add_argument(
        "--file", type=str, help="从文件读取专辑ID列表（每行一个ID）"
    )
    album_parser.add_argument(
        "keyword", nargs="?", type=str, help="专辑名称（可选，不提供--id时使用）"
    )

    args = parser.parse_args()

    if args.command == "list":
        albums = list_albums()
        table = Table(title="专辑列表")
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="green")

        for album in albums:
            table.add_row(album.get("cid", ""), album.get("name", ""))

        console.print(table)

    elif args.command == "all":
        albums = list_albums()
        album_ids = [album.get("cid", "") for album in albums]
        to_flac = getattr(args, "flac", False)

        if to_flac and not MUTAGEN_AVAILABLE:
            console.print(
                "[yellow]转换FLAC需要安装 mutagen: pip install mutagen[/yellow]"
            )
            to_flac = False

        console.print(f"[bold]即将下载所有专辑，共 {len(album_ids)} 个[/bold]")
        if to_flac:
            console.print(f"[yellow]FLAC模式: 开启[/yellow]")
        console.print()
        confirm = input("确认下载？(y/N): ").strip().lower()

        if confirm != "y" and confirm != "yes":
            console.print("[yellow]已取消[/yellow]")
            return

        console.print(f"\n[bold]开始下载...[/bold]\n")
        success_count = 0
        failed_count = 0

        try:
            for i, album_id in enumerate(album_ids, 1):
                console.print(
                    f"[cyan]========== [{i}/{len(album_ids)}] 专辑 {album_id} ==========[/cyan]"
                )
                try:
                    download_album(album_id, args.path, to_flac)
                    success_count += 1
                except Exception as e:
                    console.print(f"[red]下载失败: {album_id} - {e}[/red]")
                    failed_count += 1
                console.print()
        except KeyboardInterrupt:
            console.print("\n[yellow]已取消[/yellow]")
            return

        console.print(f"[bold green]========== 全部下载完成 ==========[/bold green]")
        console.print(f"[green]成功: {success_count}/{len(album_ids)}[/green]")
        if failed_count > 0:
            console.print(f"[red]失败: {failed_count}[/red]")

    elif args.command == "search":
        results = search_albums(args.keyword)
        table = Table(title=f"搜索结果 ({len(results)} 个)")
        table.add_column("ID", style="cyan")
        table.add_column("名称", style="green")

        for album in results:
            table.add_row(album.get("cid", ""), album.get("name", ""))

        console.print(table)

    elif args.command == "album":
        # 检查FLAC选项
        to_flac = getattr(args, "flac", False)
        if to_flac and (not PYDUB_AVAILABLE or not MUTAGEN_AVAILABLE):
            console.print(
                "[yellow]转换FLAC需要安装 pydub 和 mutagen: pip install pydub mutagen[/yellow]"
            )
            to_flac = False

        # 批量下载模式
        album_ids = []

        # 从 --ids 参数获取
        if getattr(args, "ids", None):
            album_ids = [id.strip() for id in args.ids.split(",") if id.strip()]

        # 从 --file 参数读取
        if getattr(args, "file", None):
            try:
                with open(args.file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            album_ids.append(line)
            except Exception as e:
                console.print(f"[red]读取文件失败: {e}[/red]")
                return

        # 如果有批量ID列表
        if album_ids:
            console.print(f"[bold]批量下载模式，共 {len(album_ids)} 个专辑[/bold]\n")
            success_count = 0
            failed_count = 0
            try:
                for i, album_id in enumerate(album_ids, 1):
                    console.print(
                        f"[cyan]========== [{i}/{len(album_ids)}] 专辑 {album_id} ==========[/cyan]"
                    )
                    try:
                        download_album(album_id, args.path, to_flac)
                        success_count += 1
                    except Exception as e:
                        console.print(f"[red]下载失败: {album_id} - {e}[/red]")
                        failed_count += 1
                    console.print()
            except KeyboardInterrupt:
                console.print("\n[yellow]已取消[/yellow]")
                return
            console.print(
                f"[bold green]========== 批量下载完成 ==========[/bold green]"
            )
            console.print(f"[green]成功: {success_count}/{len(album_ids)}[/green]")
            if failed_count > 0:
                console.print(f"[red]失败: {failed_count}[/red]")
            return

        # 如果提供了--id，直接下载
        if args.id:
            try:
                download_album(args.id, args.path, to_flac)
            except KeyboardInterrupt:
                console.print("\n[yellow]已取消[/yellow]")
        # 如果提供了keyword但没有--id，搜索并尝试自动匹配
        elif args.keyword:
            results = search_albums(args.keyword)
            if not results:
                console.print(f"[red]未找到匹配的专辑: {args.keyword}[/red]")
                return

            # 检查是否完全匹配
            exact_match = None
            for album in results:
                if album.get("name", "").lower() == args.keyword.lower():
                    exact_match = album
                    break

            if exact_match:
                console.print(
                    f"[green]找到精确匹配: {exact_match.get('name')} (ID: {exact_match.get('cid')})[/green]"
                )
                try:
                    download_album(exact_match.get("cid"), args.path, to_flac)
                except KeyboardInterrupt:
                    console.print("\n[yellow]已取消[/yellow]")
            elif len(results) == 1:
                # 只有一个结果，直接下载
                album = results[0]
                console.print(
                    f"[green]只有一个结果: {album.get('name')} (ID: {album.get('cid')})[/green]"
                )
                try:
                    download_album(album.get("cid"), args.path, to_flac)
                except KeyboardInterrupt:
                    console.print("\n[yellow]已取消[/yellow]")
            else:
                # 显示搜索结果供用户选择
                table = Table(title="搜索结果")
                table.add_column("ID", style="cyan")
                table.add_column("名称", style="green")
                for album in results:
                    table.add_row(album.get("cid", ""), album.get("name", ""))
                console.print(table)
                console.print(
                    f"[yellow]找到 {len(results)} 个结果，请使用[/yellow] [bold]--id[/bold] [yellow]指定专辑ID[/yellow]"
                )
        else:
            parser.parse_args(["album", "-h"])

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
