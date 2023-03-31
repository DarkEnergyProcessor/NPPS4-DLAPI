NPPS4-DLAPI
=====

This is reference implementation and documentation of NPPS4 Download API protocol.

Setup
-----

Before running, ensure to have all SIF game files with these structure.

```
<project root>
├── archive-root/
│   ├── {iOS,Android}/
│   │   ├── update/
│   │   │   ├── <client_version>/
│   │   │   │   ├── external/
│   │   │   │   │   ├── assets/
│   │   │   │   │   ├── db/
│   │   │   │   │   └── en/
│   │   │   │   ├── 1.zip
│   │   │   │   ├── 2.zip
│   │   │   │   ├── ...
│   │   │   │   └── info.json
│   │   │   └── info.json
│   │   └── package/
│   │       ├── <client_version>/
│   │       │   ├── <package_type>/
│   │       │   │   ├── <package_id>/
│   │       │   │   │   ├── 1.zip
│   │       │   │   │   ├── 2.zip
│   │       │   │   │   ├── ...
│   │       │   │   │   └── info.json
│   │       │   │   └── info.json
│   │       │   └── microdl_map.json
│   │       └── info.json
│   └── release_info.json
└── n4dlapi/
    ├── main.py
    └── ...
```

### Explanation, all paths are relative to `archive-root`:

* `release_info.json` - Contains all keys used to decrypt game database rows.

* `{iOS,Android}` - Must be either `iOS` or `Android`. Will be referred to `<OS>` from now on.

* `<OS>/update/info.json` - Contains list of available client versions in this update package, as an array.

* `<OS>/update/<client_version>` - Contains necessary file for version update to `<client_version>`. Note that updates are not incremental, so for example, updating from version 59.0 to 59.4 will require serving all files for 59.1, 59.2, 59.3, and 59.4, in that order.

* `<OS>/update/<client_version>/info.json` - Contains list of files for specific update version package, relative to `<OS>/update/<client_version>` directory, where the key is the filename and the value is the file size. The order follows the filename such that `2.zip` comes **after** `1.zip`, not `10.zip` (this sorting order will be referred to "natural sort" from now on).

* `<OS>/update/<client_version>/external` - Contains extracted update files. Not needed.

* `<OS>/package/info.json` - Contains list of all fully downloaded packages by `<client_version>`.

* `<OS>/package/<client_version>/microdl_map.json` - Contains mapping of files which are served using micro download functionality. The key is the asset filename and the value is the archive path where this file reside, including the `archive-root/` directory.

* `<OS>/package/<client_version>/<package_type>/info.json` - Contains list of `<package_id>`s for the corresponding `<package_type>`.

* `<OS>/package/<client_version>/<package_type>/<package_id>/info.json` - Contains list of files for specific package type and id at specific client version, relative to `<OS>/update/<client_version>` directory, where the key is the filename and the value is the file size. Ordered by natural sorting order.

### Example `release_info.json`:

```json
{
	"423": "UDKkj/dmBRbz+CIB+Ekqyg==",
	"1870": "Lckl38UoH8CfOMqMSmMYsA==",
	"1871": "acAmAWyPOCrO+R5qY9UTtQ=="
}
```

### Example `<OS>/update/info.json`

```json
["59.1", "59.2", "59.3", "59.4"]
```

### Example `<OS>/update/info.json`

```json
{
	"1.zip": 12237086,
	"2.zip": 8725394,
	"3.zip": 1612,
	"4.zip": 318
}
```

### Example `<OS>/package/info.json`

```json
["59.1", "59.2", "59.3", "59.4"]
```

### Example `<OS>/package/<client_version>/microdl_map.json`, 10 data, random order

```json
{
	// ...
	"en/assets/image/sticker/tx_st_107_006.texb": "archive-root/iOS/package/59.4/4/0/336.zip",
	"en/assets/image/secretbox/navi/tx_navi_77711124.texb": "archive-root/iOS/package/59.4/4/0/66.zip",
	"assets/image/secretbox/appeal/tx_appeal_1255_a.texb": "archive-root/iOS/package/59.4/4/1820/1.zip",
	"en/assets/image/secretbox/appeal/tx_appeal_1485_b.texb": "archive-root/iOS/package/59.4/4/0/277.zip",
	"assets/image/units/tx_u_normal_card_52003002.texb": "archive-root/iOS/package/59.4/4/147/1.zip",
	"assets/image/secretbox/title/tx_title_366_7.texb": "archive-root/iOS/package/59.4/4/1262/1.zip",
	"en/assets/image/secretbox/appeal/tx_appeal_9991387.texb": "archive-root/iOS/package/59.4/4/0/37.zip",
	"assets/image/multi_unit/scenario/tx_ch_ms_002_001.texb": "archive-root/iOS/package/59.4/4/248/1.zip",
	"assets/image/units/tx_u_normal_navi_42002002.texb": "archive-root/iOS/package/59.4/4/0/130.zip",
	"assets/sound/voice/navi/vo_na_106_0604.mp3": "archive-root/iOS/package/59.4/4/0/328.zip"
	// ...
}
```

Note: Usually the `microdl_map.json` is 7MB in size.

### Example `<OS>/package/<client_version>/<package_type>/info.json`, where `<package_type>` is 1

```json
[
	578, 579, 580, 583, 584, 585, 587, 588, 589, 590, 591, 592, 593, 594, 595, 596, 597, 598, 599, 600, 601, 602, 603,
	604, 605, 606, 607, 614, 622, 623, 624, 625, 626, 627, 628, 629, 630, 631, 633, 634, 635, 636, 637, 638, 639, 640,
	641, 642, 643, 644, 645, 646, 647, 648, 649, 652, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665,
	666, 667, 668, 669, 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 680, 681, 682, 683, 684, 685, 686, 687, 688,
	689, 690, 691, 692, 693, 694, 695, 696, 697, 698, 699, 700, 701, 702, 703, 704, 705, 706, 707, 708, 709, 710, 712,
	714, 715, 716, 717, 718, 719, 720, 721, 722, 723, 724, 725, 726, 727, 728, 729, 730, 731, 732, 733, 734, 735, 736,
	737, 738, 739, 740, 741, 742, 743, 744, 745, 746, 747, 748, 749, 750, 751, 752, 753, 754, 755, 756, 757, 758, 759,
	760, 761
]
```

### Example `<OS>/package/<client_version>/<package_type>/<package_id>/info.json`, where `<package_type>` is 1 and `<package_id>` is 747

```json
{
	"1.zip": 2131514,
	"2.zip": 198
}
```

Protocol
-----

Anyone are allowed to implement NPPS4 DLAPI protocol without subject to zlib license restrictions.

### Shared Key

To protect from rogue requests, the DLAPI server can be protected using shared key. This is done by
requiring `DLAPI-Shared-Key` header to match with the server-configured one. If it doesn't match, then
a 404 will be returned for all API endpoints.

<details>
<summary><code>GET</code> <code><b>/api/publicinfo</b></code></summary>

Retrieve information about the DLAPI server. A special configuration can be specified to
always serve this public information without shared key header.

#### Parameters

> None


#### Responses

```jsonc
// HTTP Code 200
{
	// Can the API be accessed publicly?
	// This can still be false even if this endpoint is accessible.
	"publicApi": true,
	// NPPS4-DLAPI API compilance version.
	// Note that there's no "patch" version. Only "major" and "minor" version.
	"dlapiVersion": {
		"major": 1,
		"minor": 0
	},
	// How long the download link will last (in seconds)? 0 means last indefinitely.
	"serveTimeLimit": 0,
	// What's the latest game version?
	"gameVersion": "59.4",

	"application": {
		// Application-specific data goes here.
	}
}
```

</details>

<details>
<summary><code>POST</code> <code><b>/api/v1/update</b></code></summary>

Get download links for update package to the latest version available.

#### Parameters

> | name      | type     | data type      | description                              |
> |-----------|----------|----------------|------------------------------------------|
> | version   | required | string         | Old client version                       |
> | platform  | required | int            | Platform type. 1 for iOS, 2 for Android. |

#### Responses

```jsonc
// HTTP Code 200
[
	// ... more items
	// For each item in this array
	{
		// Direct link to download.
		// Link must be publicly accessible even without Shared Key header.
		"url": "http://localhost/download/update_59.4.zip",
		// Archive size in bytes.
		"size": 12345,
		"checksums": {
			// For checksums, MD5 and SHA256 is required.
			// Other checksums for application-specific usage is allowed.
			"md5": "d41d8cd98f00b204e9800998ecf8427e",
			"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		}
	}
	// ... more items
]
```

</details>

<details>
<summary><code>POST</code> <code><b>/api/v1/batch</b></code></summary>

Get all download links of package IDs for specific package type.

#### Parameters

> | name         | type     | data type | description                                        |
> |--------------|----------|-----------|----------------------------------------------------|
> | package_type | required | int       | Package type. See below for valid `package_type`s. |
> | platform     | required | int       | Platform type. 1 for iOS, 2 for Android.           |

#### Possible HTTP Code

* 200 - Request is fulfilled.
* 404 - Package not found.

#### Responses

```jsonc
// HTTP Code 200
[
	// ... more items
	// For each item in this array
	{
		// Direct link to download.
		// Link must be publicly accessible even without Shared Key header.
		"url": "http://localhost/download/0_0_59.4.zip",
		// The package ID group of this archive.
		"packageId": 0,
		// Archive size in bytes.
		"size": 12345,
		"checksums": {
			// For checksums, MD5 and SHA256 is required.
			// Other checksums for application-specific usage is allowed.
			"md5": "d41d8cd98f00b204e9800998ecf8427e",
			"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		}
	}
	// ... more items
]
```

</details>

<details>
<summary><code>POST</code> <code><b>/api/v1/download</b></code></summary>

Get download links for specific package type and package id.

#### Parameters

> | name         | type     | data type | description                                        |
> |--------------|----------|-----------|----------------------------------------------------|
> | package_type | required | int       | Package type. See below for valid `package_type`s. |
> | package_id   | required | int       | Package ID.   See below for valid `package_id`s.   |
> | platform     | required | int       | Platform type. 1 for iOS, 2 for Android.           |

#### Possible HTTP Code

* 200 - Request is fulfilled.
* 404 - Package not found.

#### Responses

```jsonc
// HTTP Code 200
[
	// ... more items
	// For each item in this array
	{
		// Direct link to download.
		// Link must be publicly accessible even without Shared Key header.
		"url": "http://localhost/download/0_0_59.4.zip",
		// Archive size in bytes.
		"size": 12345,
		"checksums": {
			// For checksums, MD5 and SHA256 is required.
			// Other checksums for application-specific usage is allowed.
			"md5": "d41d8cd98f00b204e9800998ecf8427e",
			"sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
		}
	}
	// ... more items
]
```

</details>

<details>
<summary><code>POST</code> <code><b>/api/v1/getdb</b></code></summary>

Get decrypted database file.

#### Parameters

> | name | type     | data type | description          |
> |------|----------|-----------|----------------------|
> | name | required | string    | Name of the database |

#### Possible HTTP Code

* 302 - Request is fulfilled. Location header refers to the DB file. Requires Shared Key header to download if set.
* 404 - Database not found.

</details>


### List of valid `<package_type>`s and where to find the `<package_id>`s:

* 0: Always 0.
* 1: `live_track_id` column in `live_track_m` table in `live/live.db_`
* 2: `scenario_chapter_id` column in `scenario_chapter_m` table in `scenario/scenario.db_`.
* 3: `unit_id` column in `subscenario_m` table in `subscenario/subscenario.db_`.
* 4: Not available. All possible package_id is stored server-side and only exposed at certain times at `release_info.json` key ID.
* 5: `event_scenario_id` column in `event_scenario_m` table in `event/event_common.db_`.
* 6: `multi_unit_scenario_id` column in `multi_unit_scenario_m` table in `multi_unit_scenario/multi_unit_scenario.db_`.

Note: `included_pkg_m` in `bootstrap.db_` contains list of preloaded packages.

Contributing
-----

Codebase in this reference implementation is formatted using [`black`](https://github.com/psf/black) formatter,
with max line of 120 lines (`-l 120`).

There's no CLA. Anyone is free to contribute.

License
-----

This reference implementation is licensed under zlib/libpng license.
