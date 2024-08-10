declare module 'm3u8-parser' {
  export interface Playlist {
    attributes: {};
    uri: string;
  }
  export interface Parser {
    push: (content: string) => void;
    end: () => void;
    manifest: {
      allowCache: boolean;
      endList: boolean;
      mediaSequence: number;
      dateRanges: [];
      discontinuitySequence: number;
      playlistType: string;
      custom: {};
      playlists: [Playlist];
      mediaGroups: {
        AUDIO: {
          'GROUP-ID': {
            NAME: {
              default: boolean;
              autoselect: boolean;
              language: string;
              uri: string;
              instreamId: string;
              characteristics: string;
              forced: boolean;
            };
          };
        };
        VIDEO: {};
        'CLOSED-CAPTIONS': {};
        SUBTITLES: {};
      };
      dateTimeString: string;
      dateTimeObject: Date;
      targetDuration: number;
      totalDuration: number;
      discontinuityStarts: [number];
      segments: [
        {
          title: string;
          byterange: {
            length: number;
            offset: number;
          };
          duration: number;
          programDateTime: number;
          attributes: {};
          discontinuity: number;
          uri: string;
          timeline: number;
          key: {
            method: string;
            uri: string;
            iv: string;
          };
          map: {
            uri: string;
            byterange: {
              length: number;
              offset: number;
            };
          };
          'cue-out': string;
          'cue-out-cont': string;
          'cue-in': string;
          custom: {};
        },
      ];
    };
  }

  export const Parser: {
    prototype: Parser;
    new (): Parser;
  };
}
