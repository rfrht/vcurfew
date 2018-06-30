# vcurfew - Keeping your guests (or kids) under control


== WORK IN PROGRESS ==

----
## What is vcurfew?
`vcurfew` aims to be a lightweight, simple, extensible network access control built on top of a sqlite database.

## How does vcurfew works?
By default, a guest (or a kid..) will have blocked internet access, redirecting traffic to  a captive portal.

The `vcurfew` tenets are:

* Each user, that can have multiple devices attached to its username, have a pre-defined internet usage window, with start of day and end of day.
* During the day, the user is entitled to a limited amount of tokens. Each token translate into a configured amount of hours. Let the practical example:

    * User Yasmin is allowed to get her internet tokens from 8A-9P. She is allowed to request 2 two-hour tokens per day, yielding maximum 4 hours of internet time a day.
    * However, in the weekend (defined as Saturday and Sunday) she is entitled to 3 tokens of 2 hours, resulting in 6 hours of internet usage during the weekends.

* When a token is issued, the internet access is authorized immediately and will be valid until the current token expires. There are provisions to avoid issuing a new token while there is still a active token.

* If balance permit, the user can request a new token and get more internet usage.

## What are the vcurfew requirements?
In order to be able to run `vcurfew`, you will need:

* A CGI-compatible web server (`apache`, `lighttpd`, <insert name here web server>)
* `sqlite`
* `at` job scheduler
* And... A router where you can run the script :-)

----
## Installing
1. Configure your web server to [serve CGI content](http://lmgtfy.com/?q=how+do+I+configure+my+web+server+to+run+cgi%3F)
2. [Download vcurfew](https://github.com/rfrht/vcurfew/archive/master.zip) and store the `cgi/vcurfew.cgi` file at the CGI directory of your favourite web server
3. Move the `etc` folder to your `/etc`, so your configuration will be in `/etc/vcurfew`
4. Discover which user runs your web server
5. You will need to [set `iptables` `sudo` capabilities](http://lmgtfy.com/?q=how+do+I+configure+passwordless+sudo%3F) to your web server user, in order to  create the rules that will allow and deny access (`¯\_(ツ)_/¯`)
6. Edit `/etc/at.allow` and add your web server username over there
7. Ensure that the `at` service is running
8. Grant the web server group write permission in `/etc/vcurfew`

## Configuring the Database
First thing, initialize your `sqlite` database:

    # sqlite /etc/vcurfew/vcurfew.db
    SQLite version 2.8.17
    Enter ".help" for instructions
    sqlite>

Create the tables:

    sqlite> CREATE TABLE history(user VARCHAR (8), epoch_consumed INTEGER, token_type TINYINT);
    sqlite> CREATE TABLE systems(mac VARCHAR (12), friendly VARCHAR (8), user VARCHAR (8));
    sqlite> CREATE TABLE tokens(user VARCHAR (8), token_epoch timestamp, token_type TINYINT);
    sqlite> CREATE TABLE users(user VARCHAR (8), duration_week INTEGER, duration_weekend INTEGER,
       ...>                    time_start INTEGER, time_end INTEGER, tokens_week INTEGER,
       ...>                    tokens_weekend INTEGER);

And to quit, type dot-q:

    sqlite> .q

## The Database Schema

### `systems`
The `systems` table enumerates all devices that are subjected to `vcurfew` control.
The structure of the `systems` table is comprised of: 

* `mac` - The MAC address (all caps, 12-character, no colons) of the device;
* `friendly`- Friendly Name for the device (8 character); 
* `user` - username of the device owner (which must correlate to the `users` table).

### `users`
The `users` tables describes the authorized usage pattern of the users (and devices).
A user record contains the following informations:

* `user` - a 8-character unique user name, which is correlated to the devices described in systems table;
* `duration_week` - How long does a weekday token last;
* `duration_weekend` - How long does a weekend token last;
* `time_start` - At what time can the user start requesting tokens (and use the internet). Format: 00-24, local time;
* `time_end` - At what time should a token be revoked and inhibit new token requests. Format: 00-24, local time;
* `tokens_week` - How many tokens can a user request per weekday
* `tokens_weekend` - How many tokens can the user request during the weekend.

### A example.
Borrowing from the opening project description, this example describes the configuration of Yasmin user, which has two devices, can use internet from 9a-10p, entitled to 2 tokens of two hours each during weekdays, and three tokens of 3 hours during weekends.

In the `users` table:

    sqlite> SELECT * FROM users WHERE user = "yasmin";
    yasmin|2|3|9|22|2|3

And then, the `systems` table:

    sqlite> SELECT * FROM systems WHERE user = "yasmin";
    77:88:99:AA:BB:CC|ipad-yaya|yasmin
    DD:EE:FF:00:AA:BB|iphone-yaya|yasmin

## Network Setup.
Describing two possible networking scenarios (of many possible).

### Everyone is denied, except the controlled devices
In this scenario, no devices are allowed in the network, except for the listed devices in the database. You set a catch-all `iptables` default negation rule and a redirect which will redirect the traffic to the HTTP server running the captive portal. Let your captive portal be 192.168.1.3:

    # iptables -I FORWARD -i eth0.4 -j DROP
    # iptables -t nat -I PREROUTING -i eth0.4 ! -d 192.168.1.3 -p tcp --dport 80 -j DNAT --to 192.168.1.3:8081

### Everyone is freely allowed, except the controlled devices
Here, you will need to first create a default negation rule of the controlled devices and then, upon starting a session, `vcurfew` will insert a `iptables` rule  which will allow internet access and drop the rule that cause the redirect. The base rules that should be always present and active are:

    # iptables -I FORWARD -i eth0.4 -m mac --mac-source 77:88:99:AA:BB:CC -j DROP
    # iptables -t nat -I PREROUTING -i eth0.4 ! -d 192.168.1.3 -m mac --mac-source 77:88:99:AA:BB:CC -p tcp --dport 80 -j DNAT --to 192.168.1.3:8081

## The captive portal.
In order to be friendly with your network devices (and better user experience), the `iptables` will intercept the traffic to a local HTTP server and cause a HTTP 302 redirect to the traffic. That will (should) trigger a captive portal login in your device.
If using `lighttpd`, there are a few suggesting configurations, in order to redirect the traffic to `vcurfew`:

* There's a instance listening in port 8081 acting as a catch-all and then redirecting (via HTTP 302) to the correct URL of the captive portal.
* And then it is redirected to the standard port 80 cgi-bin URL.

```
$SERVER["socket"] == "192.168.1.3:8081" {
    $HTTP["host"] =~ "^(.*)$" {
        url.redirect = ( "^/(.*)" => "http://192.168.1.3/cgi-bin/vcurfew.cgi" )
        url.redirect-code = 302
    }
}
```

## TODO
* Web UI for user
* Web UI for admin
* User Balance web page
* User History web page
* Admin add Credit tokens
* Emergency tokens
