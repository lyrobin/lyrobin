from ai.batch import audio_transcribe
from unittest import mock
import unittest
from legislature import models
import uuid
from firebase_admin import firestore  # type: ignore

TRANSCRIPT = """\
00:12 - 00:20 好各位我們線上所有的好朋友,我們各位官員,各位國人同胞,昨天看到賴總統的文告,
00:26 - 00:33 我覺得賴總統講的國家要團結,社會要安定。
00:34 - 00:38 賴總統昨天在文告中啊,講得非常清楚,我也認同,
00:41 - 00:57 但是我在這裡更認同的一句話是國家利益永遠高於政黨利益,政黨利益永遠不能凌駕人民的利益,這我拍拍手。
01:01 - 01:16 那我要請教賴總統,你就職以來,你的幻化造謠,打壓政敵,製造對立,在國人都是再找敵人,這等等,我請問你這次說的文告是真,
01:18 - 01:25 的或假的,所以賴總統你能不能做給我們看一看,千萬不要講一套做一套。
01:37 - 01:44 那現在未來,我就要請教我們最敬愛的卓院長,賴總統的話,你聽不聽？
01:45 - 01:50 所以賴總統已經講出這些話,那你到底要不要聽他的話,在整個施政,在立法院的關係如何去改,
01:51 - 01:58 變,你要不要有所作為,那我現在只有問三個敏感的問題,第一個,
02:02 - 02:07 原住民的進法補償,那你到底變不變？
02:08 - 02:14 第二個,農民的公糧收購漲五塊錢,那你到底變不變？
02:15 - 02:22 另外一個,國會改革的部分,你試現到底測不測,所以這三點,我請卓院長做施政的參考。
02:29 - 02:34 當然我們希望賴總統卓院長以及執政的所有的同仁,我相信你們一定要有誠意放下屠刀,
02:41 - 02:50 立地誠懇的個性,所以台灣人民多數都希望兩岸和平,政黨和解,
02:51 - 03:06 人民安定,百姓樂利,更希望執政黨要以以民為念,始出善意,達到台灣安和樂利的台灣,所以在這裡我還是要拜託執政黨,賴總統已經講了,立地誠懇,
03:14 - 03:17 把所有屠刀放下,政黨才會和。
"""

EXPECTED_TRANSCRIPT = """\
好各位我們線上所有的好朋友,我們各位官員,各位國人同胞,昨天看到賴總統的文告,
我覺得賴總統講的國家要團結,社會要安定。
賴總統昨天在文告中啊,講得非常清楚,我也認同,
但是我在這裡更認同的一句話是國家利益永遠高於政黨利益,政黨利益永遠不能凌駕人民的利益,這我拍拍手。
那我要請教賴總統,你就職以來,你的幻化造謠,打壓政敵,製造對立,在國人都是再找敵人,這等等,我請問你這次說的文告是真,
的或假的,所以賴總統你能不能做給我們看一看,千萬不要講一套做一套。
那現在未來,我就要請教我們最敬愛的卓院長,賴總統的話,你聽不聽？
所以賴總統已經講出這些話,那你到底要不要聽他的話,在整個施政,在立法院的關係如何去改,
變,你要不要有所作為,那我現在只有問三個敏感的問題,第一個,
原住民的進法補償,那你到底變不變？
第二個,農民的公糧收購漲五塊錢,那你到底變不變？
另外一個,國會改革的部分,你試現到底測不測,所以這三點,我請卓院長做施政的參考。
當然我們希望賴總統卓院長以及執政的所有的同仁,我相信你們一定要有誠意放下屠刀,
立地誠懇的個性,所以台灣人民多數都希望兩岸和平,政黨和解,
人民安定,百姓樂利,更希望執政黨要以以民為念,始出善意,達到台灣安和樂利的台灣,所以在這裡我還是要拜託執政黨,賴總統已經講了,立地誠懇,
把所有屠刀放下,政黨才會和。"""


class TestOnReceiveAudioTranscript(unittest.TestCase):

    @mock.patch("ai.batch.audio_transcribe.start_generate_hashtags")
    @mock.patch("ai.batch.audio_transcribe.start_summarize_transcript")
    def test_clean_up_transcript(
        self,
        mock_start_summarize_transcript: mock.Mock,
        mock_start_generate_hashtags: mock.Mock,
    ):
        mock_response = mock.MagicMock()
        mock_response.text = TRANSCRIPT
        uid = uuid.uuid4().hex
        doc_path = f"{models.MEETING_COLLECT}/{uid}/speeches/0"
        db = firestore.client()
        ref = db.document(doc_path)
        ref.set(
            models.Video(
                audios=["gs://bucket/audio.mp3"],
            ).asdict()
        )

        audio_transcribe.on_receive_audio_transcript(mock_response, doc_path)
        video = models.Video.from_dict(ref.get().to_dict())
        segments = [
            models.SpeechSegment.from_dict(doc.to_dict())
            for doc in ref.collection(models.SPEECH_SEGMENT_COLLECT)
            .order_by("start", direction="ASCENDING")
            .stream()
        ]

        mock_start_summarize_transcript.assert_called_once()
        mock_start_generate_hashtags.assert_called_once()
        self.assertEqual(len(segments), 16)
        self.assertEqual(segments[0].start, "00:12")
        self.assertEqual(video.transcript, EXPECTED_TRANSCRIPT)
