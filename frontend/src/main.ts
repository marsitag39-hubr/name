import { bootstrapApplication } from '@angular/platform-browser';
import { registerLocaleData } from '@angular/common';
import localeEsMx from '@angular/common/locales/es-MX';
import { LOCALE_ID } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app/app.component';

registerLocaleData(localeEsMx);
bootstrapApplication(AppComponent, { providers: [provideHttpClient(), { provide: LOCALE_ID, useValue: 'es-MX' }] }).catch(err => console.error(err));
