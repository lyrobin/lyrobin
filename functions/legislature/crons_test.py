import unittest
import datetime as dt
from unittest import mock
from legislature import crons
from legislature import models
from firebase_admin import firestore  # type: ignore


class TestGenerateWeeklyReport(unittest.TestCase):

    @mock.patch.object(crons.langchain, "generate_weekly_news_titles")
    def test_generate_weekly_report(self, mock_generate_weekly_news_titles):
        mock_generate_weekly_news_titles.return_value = [
            "新聞標題 1",
            "新聞標題 2",
        ]

        start = dt.datetime(2024, 2, 22)
        end = dt.datetime(2024, 2, 23)
        crons._generate_weekly_report(start, end)

        week_date = start.isocalendar()[1]

        db = firestore.client()
        m = models.WeeklyReport.from_dict(
            db.collection(models.WEEKLY_COLLECT)
            .document(str(week_date))
            .get()
            .to_dict()
        )

        self.assertEqual(m.week, week_date)
        self.assertSetEqual(
            set(m.titles),
            set(
                [
                    "新聞標題 1",
                    "新聞標題 2",
                ]
            ),
        )
