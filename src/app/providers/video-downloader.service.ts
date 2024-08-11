import { Injectable } from '@angular/core';
import { FFmpeg } from '@ffmpeg/ffmpeg';
import { FFMessageLoadConfig, FileData } from '@ffmpeg/ffmpeg/dist/esm/types';
import { fetchFile, toBlobURL } from '@ffmpeg/util';
import { Parser } from 'm3u8-parser';
import { v4 as uuidv4 } from 'uuid';

@Injectable({
  providedIn: 'root',
})
export class VideoDownloaderService {
  private ffmpegLoaded = false;
  private downloading = false;
  private ffmpeg?: FFmpeg;
  private readonly ffmpegMultithreadBaseURL =
    'https://unpkg.com/@ffmpeg/core-mt@0.12.6/dist/esm';
  private readonly ffmpegBaseURL =
    'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm';
  private readonly batchSize = 20;

  constructor() {}

  async loadFFmpegConfig(): Promise<FFMessageLoadConfig> {
    if (crossOriginIsolated) {
      return {
        coreURL: await toBlobURL(
          `${this.ffmpegMultithreadBaseURL}/ffmpeg-core.js`,
          'text/javascript'
        ),
        wasmURL: await toBlobURL(
          `${this.ffmpegMultithreadBaseURL}/ffmpeg-core.wasm`,
          'application/wasm'
        ),
        workerURL: await toBlobURL(
          `${this.ffmpegMultithreadBaseURL}/ffmpeg-core.worker.js`,
          'text/javascript'
        ),
        classWorkerURL: '/assets/ffmpeg/worker.js',
      };
    } else {
      return {
        coreURL: await toBlobURL(
          `${this.ffmpegBaseURL}/ffmpeg-core.js`,
          'text/javascript'
        ),
        wasmURL: await toBlobURL(
          `${this.ffmpegBaseURL}/ffmpeg-core.wasm`,
          'application/wasm'
        ),
        classWorkerURL: '/assets/ffmpeg/worker.js',
      };
    }
  }

  async loadFFmpeg(): Promise<FFmpeg> {
    if (!this.ffmpegLoaded) {
      this.ffmpeg = new FFmpeg();
      this.ffmpeg.on('log', ({ message }) => {
        console.log(message);
      });
      const config = await this.loadFFmpegConfig();
      this.ffmpegLoaded = await this.ffmpeg.load(config);
    }
    return this.ffmpeg!;
  }

  private downloadPlaylist(
    ffmpeg: FFmpeg,
    dir: string,
    url: string
  ): Promise<Parser> {
    const filename = url.split('/').pop();
    return fetch(url, { mode: 'cors' })
      .then(res => res.blob())
      .then(blob => {
        return new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = e => {
            if (!e.target) {
              reject(`Fail to read file: ${url}`);
            } else {
              resolve(e.target?.result as string);
            }
          };
          reader.readAsText(blob);
        });
      })
      .then(manifest => {
        ffmpeg.writeFile(`${dir}/${filename}`, manifest);
        const parser = new Parser();
        parser.push(manifest);
        return parser;
      });
  }

  private downloadToFFmpeg(
    ffmpeg: FFmpeg,
    dir: string,
    url: string
  ): Promise<string> {
    const filename = url.split('/').pop();
    return fetchFile(url).then(data => {
      ffmpeg.writeFile(`${dir}/${filename}`, data);
      return `${dir}/${filename}`;
    });
  }

  private async downloadSegments(
    ffmpeg: FFmpeg,
    dir: string,
    baseURL: string,
    parser: Parser
  ) {
    for (let i = 0; i < parser.manifest.segments.length; i += this.batchSize) {
      const downloads = [];
      for (const s of parser.manifest.segments.slice(i, i + this.batchSize)) {
        downloads.push(
          this.downloadToFFmpeg(ffmpeg, dir, `${baseURL}/${s.uri}`)
        );
      }
      await Promise.all(downloads);
    }
  }

  private triggerFileDownloadForUser(data: FileData) {
    const url = URL.createObjectURL(new Blob([data], { type: 'video/mp4' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'video.mp4';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  private async downloadMP4FromPlaylist(ffmpeg: FFmpeg, url: string) {
    const baseURL = url.split('/').slice(0, -1).join('/');
    const dir = `/${uuidv4()}`;
    ffmpeg.createDir(dir);
    const playlistName = url.split('/').pop();
    const playlist = await this.downloadPlaylist(ffmpeg, dir, url);
    const chunksName = playlist.manifest.playlists[0].uri;
    const chunks = await this.downloadPlaylist(
      ffmpeg,
      dir,
      `${baseURL}/${chunksName}`
    );
    await this.downloadSegments(ffmpeg, dir, baseURL, chunks);
    await ffmpeg.exec([
      '-i',
      `${dir}/${playlistName}`,
      '-c',
      'copy',
      `${dir}/video.mp4`,
    ]);
    const data = await ffmpeg.readFile(`${dir}/video.mp4`);
    this.triggerFileDownloadForUser(data);
    return ffmpeg.listDir(dir).then(async files => {
      for (const f of files) {
        if (!f.isDir) {
          await ffmpeg.deleteFile(`${dir}/${f.name}`);
        }
      }
      await ffmpeg.deleteDir(dir);
    });
  }

  downloadFromPlaylist(url: string): Promise<void> {
    if (this.downloading) {
      throw new Error('Already have a downloading task.');
    }
    this.downloading = true;
    return this.loadFFmpeg()
      .then(ffmpeg => this.downloadMP4FromPlaylist(ffmpeg, url))
      .finally(() => {
        this.downloading = false;
      });
  }
}
