import { Component } from '@angular/core';

@Component({
  selector: 'app-github-icon',
  standalone: true,
  imports: [],
  template: `
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg">
      <path
        d="M10 0.24762C4.475 0.24762 0 4.72512 0 10.2476C0 14.6668 2.865 18.4143 6.8375 19.7351C7.3375 19.8293 7.52083 19.5201 7.52083 19.2543C7.52083 19.0168 7.5125 18.3876 7.50833 17.5543C4.72667 18.1576 4.14 16.2126 4.14 16.2126C3.685 15.0585 3.0275 14.7501 3.0275 14.7501C2.12167 14.1301 3.0975 14.1426 3.0975 14.1426C4.10167 14.2126 4.62917 15.1726 4.62917 15.1726C5.52083 16.7018 6.97 16.2601 7.54167 16.0043C7.63167 15.3576 7.88917 14.9168 8.175 14.6668C5.95417 14.4168 3.62 13.5568 3.62 9.72512C3.62 8.63345 4.0075 7.74179 4.64917 7.04179C4.53667 6.78929 4.19917 5.77262 4.73667 4.39512C4.73667 4.39512 5.57417 4.12679 7.48667 5.42012C8.28667 5.19762 9.13667 5.08762 9.98667 5.08262C10.8367 5.08762 11.6867 5.19762 12.4867 5.42012C14.3867 4.12679 15.2242 4.39512 15.2242 4.39512C15.7617 5.77262 15.4242 6.78929 15.3242 7.04179C15.9617 7.74179 16.3492 8.63345 16.3492 9.72512C16.3492 13.5668 14.0117 14.4126 11.7867 14.6585C12.1367 14.9585 12.4617 15.5718 12.4617 16.5085C12.4617 17.8468 12.4492 18.9218 12.4492 19.2468C12.4492 19.5093 12.6242 19.8218 13.1367 19.7218C17.1375 18.4101 20 14.6601 20 10.2476C20 4.72512 15.5225 0.24762 10 0.24762Z"
        fill="currentColor"
        fillOpacity="0.5" />
    </svg>
  `,
})
export class GithubIconComponent {}
