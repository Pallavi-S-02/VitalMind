const http = require('http');

const data = JSON.stringify({
  email: 'dr.mehta@vitalmind.com',
  password: 'Doctor123!'
});

const options = {
  hostname: '127.0.0.1',
  port: 5000,
  path: '/api/v1/auth/login',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': data.length
  }
};

const req = http.request(options, res => {
  let body = '';
  res.on('data', d => body += d);
  res.on('end', () => {
    const token = JSON.parse(body).token;
    console.log('Token:', token ? 'Success' : 'Fail', body);
    
    // Now fetch patient
    const req2 = http.request({
      hostname: '127.0.0.1',
      port: 5000,
      path: '/api/v1/patients/4adb29e4-bc62-4d8d-a788-05ecc8488bd1',
      method: 'GET',
      headers: { 'Authorization': 'Bearer ' + token }
    }, res2 => {
      let body2 = '';
      res2.on('data', d => body2 += d);
      res2.on('end', () => console.log('Patient API Status:', res2.statusCode, body2));
    });
    req2.end();
  });
});

req.write(data);
req.end();
