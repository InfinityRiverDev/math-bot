fetch("https://rest.kstu.ru/restapi/schedule/load-schedules/", {
  "headers": {
    "accept": "*/*",
    "accept-language": "ru,en;q=0.9",
    "authorization": "Token e65c048442312883a138af71a051e224277305ef",
    "content-type": "application/json",
    "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"YaBrowser\";v=\"26.3\", \"Yowser\";v=\"2.5\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "Referer": "https://one.kstu.ru/"
  },
  "body": "{\"year\":2025,\"list_groups\":[45029],\"id_e\":[],\"numb_week\":33}",
  "method": "POST"
});


