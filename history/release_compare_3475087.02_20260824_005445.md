# EVE SDE Build 3475087.02 - 版本比较报告

**构建时间**: 2026-08-24 00:53:22

## 图标文件比较

本次更新未发现图标文件变更。

## 数据库比较

### 单库 (item_db.sqlite)

**数据库差异摘要**:
- 语句总数: 18920
- INSERT: 18824 / UPDATE: 56 / DELETE: 0 / 其他: 40

**按表统计**（差异）:

| 表 | INSERT | UPDATE | DELETE | 合计 |
|---|---|---|---|---|
| certificateSkills | 902 | 0 | 0 | 902 |
| certificates | 139 | 0 | 0 | 139 |
| masteries | 17780 | 0 | 0 | 17780 |
| sqlite_stat1 | 3 | 55 | 0 | 58 |
| version_info | 0 | 1 | 0 | 1 |

**差异样例**（前 200 行）:
```sql
CREATE TABLE certificateSkills (
                certificateID INTEGER NOT NULL,
                skillID INTEGER NOT NULL,
                basic INTEGER NOT NULL DEFAULT 0,
                standard INTEGER NOT NULL DEFAULT 0,
                improved INTEGER NOT NULL DEFAULT 0,
                advanced INTEGER NOT NULL DEFAULT 0,
                elite INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (certificateID, skillID)
            ) WITHOUT ROWID
        ;
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3300,3,4,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3303,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,11083,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(50,12213,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3300,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3303,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3306,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,12204,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(64,12214,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3303,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3306,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3309,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3315,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,3317,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,12205,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(65,12215,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3303,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3306,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3309,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3310,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3315,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3316,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,3317,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,20327,1,2,3,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,41407,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(66,41408,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3300,3,4,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3301,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,11082,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(67,12210,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3300,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3301,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3304,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,12206,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(68,12211,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3301,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3304,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3307,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3315,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3316,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,3317,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,12207,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(69,12212,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3301,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3304,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3307,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3310,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3315,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3316,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,3317,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,21666,1,2,3,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,41405,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(70,41406,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3300,3,4,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3302,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,11084,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(71,12201,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3300,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3302,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3305,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3311,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3312,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,3317,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,12202,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(72,12208,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3302,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3305,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3308,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3310,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3315,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,3317,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,12203,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(73,12209,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3300,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3302,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3305,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3308,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3310,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3311,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3315,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,3317,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,21667,1,2,3,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,41403,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(74,41404,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,3319,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,3320,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,3321,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,12441,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,12442,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,20209,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,20210,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,20312,0,0,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,20314,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,20315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(75,21071,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,3319,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,3321,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,3324,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,12441,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,12442,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,20211,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,20312,0,0,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,20314,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,20315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,21071,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,25718,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(76,25719,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,3319,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,3321,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,3324,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,3325,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,3326,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,12441,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,12442,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,20212,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,20213,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,20312,0,0,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,20314,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,20315,0,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(77,21071,1,3,4,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3300,2,2,2,2,2);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3319,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3321,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3324,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3325,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,3326,5,5,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,12441,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,12442,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,20312,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,20314,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,20315,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,21071,1,3,4,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,21668,1,2,3,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,32435,1,2,3,4,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,41409,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(78,41410,0,0,0,1,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(79,3319,3,4,5,5,5);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(79,3321,3,3,3,3,3);
INSERT INTO certificateSkills(certificateID,skillID,basic,standard,improved,advanced,elite) VALUES(79,3324,3,3,3,3,3);
-- ... 另有 18720 行未列出
```

## 地图和本地化文件比较

### regions_data.json

文件无差异

### systems_data.json

文件无差异

### neighbors_data.json

文件无差异

## 本地化文件比较

### accountingentrytypes_localized.json

文件无差异


## 下载文件

- **icons.zip**: 图标压缩包
- **sde.zip**: SDE数据压缩包
- **release_compare_3475087.02.md**: 详细比较报告
