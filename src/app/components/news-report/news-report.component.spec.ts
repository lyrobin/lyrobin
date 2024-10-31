import { ComponentFixture, TestBed } from '@angular/core/testing';

import { NewsReportComponent } from './news-report.component';

describe('NewsReportComponent', () => {
  let component: NewsReportComponent;
  let fixture: ComponentFixture<NewsReportComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [NewsReportComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(NewsReportComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
