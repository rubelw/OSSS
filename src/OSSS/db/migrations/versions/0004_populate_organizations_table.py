
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB are TypeDecorator; TSVectorType is PG TSVECTOR or Text
except Exception:
    # Fallbacks, in case direct import isn't available during migration
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    # JSONB shim: real JSONB on PG, JSON elsewhere
    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    # TSVECTOR shim: real TSVECTOR on PG, TEXT elsewhere
    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):  # ok to subclass for clarity
            pass
    except Exception:
        class TSVectorType(sa.Text):  # type: ignore
            pass

# revision identifiers
revision = "0004_populate_orgs_table"
down_revision = "0003_populate_states_table"
branch_labels = None
depends_on = None


organization_data = [
    ("00180000", "Adair-Casey 11070000 Chariton"),
    ("00270000", "Adel DeSoto Minburn 11160000 Charles City"),
    ("00090000", "AGWSR 11340000 Charter Oak Ute"),
    ("04410000", "A-H-S-T-W 11520000 Cherokee"),
    ("00630000", "Akron Westfield 11970000 Clarinda"),
    ("00720000", "Albert City-Truesdale 12060000 Clarion-Goldfield Dows"),
    ("00810000", "Albia 12110000 Clarke"),
    ("00990000", "Alburnett 12150000 Clarksville"),
    ("01080000", "Alden 12180000 Clay Central Everly"),
    ("01260000", "Algona 27630000 Clayton Ridge"),
    ("01350000", "Allamakee 12210000 Clear Creek Amana"),
    ("01710000", "Alta-Aurelia 12330000 Clear Lake"),
    ("02250000", "Ames 12780000 Clinton"),
    ("02340000", "Anamosa 13320000 Colfax Mingo"),
    ("02430000", "Andrew 13370000 College"),
    ("02610000", "Ankeny 13500000 Collins Maxwell"),
    ("02790000", "Aplington-Parkersburg 13590000 Colo-NESCO School"),
    ("03550000", "Ar-We-Va 13680000 Columbus"),
    ("03870000", "Atlantic 14130000 Coon Rapids Bayard"),
    ("04140000", "Audubon 14310000 Corning"),
    ("04720000", "Ballard 14760000 Council Bluffs"),
    ("05130000", "Baxter 15030000 Creston"),
    ("05400000", "BCLUW 15760000 Dallas Center Grimes"),
    ("05490000", "Bedford 16020000 Danville"),
    ("05760000", "Belle Plaine 16110000 Davenport"),
    ("05850000", "Bellevue 16190000 Davis County"),
    ("05940000", "Belmond-Klemme 16380000 Decorah"),
    ("06030000", "Bennett 16750000 Delwood"),
    ("06090000", "Benton 17010000 Denison"),
    ("06210000", "Bettendorf 17190000 Denver"),
    ("07200000", "Bondurant-Farrar 17370000 Des Moines Independent"),
    ("07290000", "Boone 17820000 Diagonal"),
    ("07470000", "Boyden-Hull 17910000 Dike-New Hartford"),
    ("19170000", "Boyer Valley 18630000 Dubuque"),
    ("08460000", "Brooklyn-Guernsey-Malcom 19080000 Dunkerton"),
    ("08820000", "Burlington 19260000 Durant"),
    ("09160000", "CAL 19440000 Eagle Grove"),
    ("09180000", "Calamus-Wheatland 19530000 Earlham"),
    ("09140000", "CAM 19630000 East Buchanan"),
    ("09360000", "Camanche 19680000 East Marshall"),
    ("09770000", "Cardinal 39780000 East Mills"),
    ("09810000", "Carlisle 67410000 East Sac County"),
    ("09990000", "Carroll 19700000 East Union"),
    ("10440000", "Cedar Falls 19720000 Eastern Allamakee"),
    ("10530000", "Cedar Rapids 19650000 Easton Valley"),
    ("10620000", "Center Point-Urbana 06570000 Eddyville-Blakesburg Fremont"),
    ("10710000", "Centerville 19890000 Edgewood Colesburg"),
    ("10800000", "Central 20070000 Eldora-New Providence"),
    ("10890000", "Central City 20880000 Emmetsburg"),
    ("10930000", "Central Decatur 20970000 English Valleys"),
    ("10820000", "Central DeWitt 21130000 Essex"),
    ("10790000", "Central Lee 21240000 Estherville Lincoln Central"),
    ("10950000", "Central Lyon 21510000 Exira-Elk Horn Kimballton"),
    ("21690000", "Fairfield 39060000 Lynnville Sully"),
    ("22950000", "Forest City 39420000 Madrid"),
    ("23130000", "Fort Dodge 40230000 Manson Northwest Webster"),
    ("23220000", "Fort Madison 40330000 Maple Valley - Anthon Oto"),
    ("23690000", "Fremont-Mills 40410000 Maquoketa"),
    ("23760000", "Galva-Holstein 40430000 Maquoketa Valley"),
    ("24030000", "Garner-Hayfield-Ventura 40680000 Marcus-Meriden Cleghorn"),
    ("24570000", "George-Little Rock 40860000 Marion"),
    ("24660000", "Gilbert 41040000 Marshalltown"),
    ("24930000", "Gilmore City-Bradgate 41220000 Martensdale-St Marys"),
    ("25020000", "Gladbrook-Reinbeck 41310000 Mason City"),
    ("25110000", "Glenwood 42030000 Mediapolis"),
    ("25200000", "Glidden-Ralston 42120000 Melcher Dallas"),
    ("26820000", "GMG 44190000 MFL MarMac"),
    ("25560000", "Graettinger-Terril 42690000 Midland"),
    ("31950000", "Greene County 42710000 Mid Prairie"),
    ("27090000", "Grinnell-Newburg 43560000 Missouri Valley"),
    ("27180000", "Griswold 41490000 MOC-Floyd Valley"),
    ("27270000", "Grundy Center 44370000 Montezuma"),
    ("27540000", "Guthrie Center 44460000 Monticello"),
    ("27720000", "Hamburg 44910000 Moravia"),
    ("27810000", "Hampton-Dumont 45050000 Mormon Trail"),
    ("28260000", "Harlan 45090000 Morning Sun"),
    ("28460000", "Harris-Lake Park 45180000 Moulton Udell"),
    ("28620000", "Hartley-Melvin-Sanborn 45270000 Mount Ayr"),
    ("29770000", "Highland 45360000 Mount Pleasant"),
    ("29880000", "Hinton 45540000 Mount Vernon"),
    ("27660000", "H-L-V 45720000 Murray"),
    ("30290000", "Howard-Winneshiek 45810000 Muscatine"),
    ("30330000", "Hubbard-Radcliffe 45990000 Nashua Plainfield"),
    ("30420000", "Hudson 46170000 Nevada"),
    ("30600000", "Humboldt 46620000 New Hampton"),
    ("31680000", "IKM-Manning 46890000 New London"),
    ("31050000", "Independence 46440000 Newell Fonda"),
    ("31140000", "Indianola 47250000 Newton"),
    ("31190000", "Interstate 35 26730000 Nodaway Valley"),
    ("31410000", "Iowa City 01530000 North Butler"),
    ("31500000", "Iowa Falls 36910000 North Cedar"),
    ("31540000", "Iowa Valley 47740000 North Fayette Valley"),
    ("31860000", "Janesville 08730000 North Iowa"),
    ("32040000", "Jesup 47780000 North Kossuth"),
    ("32310000", "Johnston 47770000 North Linn"),
    ("33120000", "Keokuk 47760000 North Mahaska"),
    ("33300000", "Keota 47790000 North Polk"),
    ("33480000", "Kingsley-Pierson 47840000 North Scott"),
    ("33750000", "Knoxville 47850000 North Tama County"),
    ("34200000", "Lake Mills 03330000 North Union"),
    ("34650000", "Lamoni 47730000 Northeast"),
    ("35370000", "Laurens-Marathon 47880000 Northwood Kensett"),
    ("35550000", "Lawton-Bronson 47970000 Norwalk"),
    ("36000000", "Le Mars 48600000 Odebolt Arthur Battle Creek Ida Grove"),
    ("36090000", "Lenox 48690000 Oelwein"),
    ("36450000", "Lewis Central 48780000 Ogden"),
    ("37150000", "Linn-Mar 48900000 Okoboji"),
    ("37440000", "Lisbon 49050000 Olin"),
    ("37980000", "Logan-Magnolia 49780000 Orient Macksburg"),
    ("38160000", "Lone Tree 49950000 Osage"),
    ("38410000", "Louisa-Muscatine 50130000 Oskaloosa"),
    ("50490000", "Ottumwa 65120000 Twin Cedars"),
    ("51210000", "Panorama 65160000 Twin Rivers"),
    ("51390000", "Paton-Churdan 65340000 Underwood"),
    ("51600000", "PCM 65360000 Union"),
    ("51630000", "Pekin 65610000 United"),
    ("51660000", "Pella 65790000 Urbandale"),
    ("51840000", "Perry 65920000 Van Buren County"),
    ("52500000", "Pleasant Valley 66150000 Van Meter"),
    ("52560000", "Pleasantville 66510000 Villisca"),
    ("52830000", "Pocahontas Area 66600000 Vinton Shellsburg"),
    ("53100000", "Postville 67000000 Waco"),
    ("54630000", "Red Oak 67590000 Wapello"),
    ("54860000", "Remsen-Union 67620000 Wapsie Valley"),
    ("55080000", "Riceville 67680000 Washington"),
    ("19750000", "River Valley 67950000 Waterloo"),
    ("55100000", "Riverside 68220000 Waukee"),
    ("56070000", "Rock Valley 68400000 Waverly-Shell Rock"),
    ("56430000", "Roland-Story 68540000 Wayne"),
    ("56970000", "Rudd-Rockford-Marble Rk 68670000 Webster City"),
    ("57240000", "Ruthven-Ayrshire 69210000 West Bend Mallard"),
    ("58050000", "Saydel 69300000 West Branch"),
    ("58230000", "Schaller-Crestland 69370000 West Burlington"),
    ("58320000", "Schleswig 69430000 West Central"),
    ("58770000", "Sergeant Bluff-Luton 62640000 West Central Valley"),
    ("58950000", "Seymour 69500000 West Delaware County"),
    ("59490000", "Sheldon 69570000 West Des Moines"),
    ("59760000", "Shenandoah 59220000 West Fork"),
    ("59940000", "Sibley-Ocheyedan 08190000 West Hancock"),
    ("60030000", "Sidney 69690000 West Harrison"),
    ("60120000", "Sigourney 69750000 West Liberty"),
    ("60300000", "Sioux Center 69830000 West Lyon"),
    ("60350000", "Sioux Central 69850000 West Marshall"),
    ("60390000", "Sioux City 69870000 West Monona"),
    ("60930000", "Solon 69900000 West Sioux"),
    ("60910000", "South Central Calhoun 69610000 Western Dubuque"),
    ("60950000", "South Hamilton 69920000 Westwood"),
    ("60990000", "South O'Brien 70020000 Whiting"),
    ("60970000", "South Page 70290000 Williamsburg"),
    ("60980000", "South Tama County 70380000 Wilton"),
    ("61000000", "South Winneshiek 70470000 Winfield-Mt Union"),
    ("61010000", "Southeast Polk 70560000 Winterset"),
    ("60960000", "Southeast Valley 70920000 Woodbine"),
    ("60940000", "Southeast Warren 70980000 Woodbury Central"),
    ("61020000", "Spencer 71100000 Woodward Granger"),
    ("61200000", "Spirit Lake 2 Iowa Accredited Nonpublic School"),
    ("61380000", "Springville 16118103 All Saints Catholic School"),
    ("57510000", "St Ansgar 10538101 All Saints School"),
    ("61650000", "Stanton 69578106 AlRazi Academy"),
    ("61750000", "Starmont 02258102 Ames Christian School"),
    ("62190000", "Storm Lake 10538212 Andrews Christian Academy"),
    ("62460000", "Stratford 02618503 Ankeny Christian Academy 7 12"),
    ("62730000", "Sumner-Fredericksburg 02618504 Ankeny Christian Academy K 6"),
    ("64080000", "Tipton 17378121 Apiary Leadership Academy"),
    ("64530000", "Treynor 69618150 Aquin Elementary School"),
    ("64600000", "Tri-Center 16118101 Assumption High School"),
    ("64620000", "Tri-County 69618146 Beckman Catholic High School"),
    ("64710000", "Tripoli 17378505 Bergman Academy"),
    ("65090000", "Turkey Valley 53108101 Bias Chaya Mushka"),
    ("01268108", "Bishop Garrigan Campus 69908311 Ireton Christian School"),
    ("60398106", "Bishop Heelan Catholic High School 10538220 Isaac Newton Christian Academy"),
    ("67958112", "Blessed Maria Assunta Pallotta Middle School 16118115 John F Kennedy Catholic School"),
    ("15768101", "Bridges Outdoor School - Dallas Center 17378014 Joshua Christian Academy"),
    ("41228101", "Bridges Outdoor School - Norwalk 17378015 Joshua Christian Academy"),
    ("37158121", "Calvary Christian Academy 17378016 Joshua Christian Academy"),
    ("60398107", "Cathedral Dual Language Academy 17378133 JW Reed Christian Academy"),
    ("10448125", "Cedar Ridge Christian School 33128115 Keokuk Catholic Schools - Saint Vincents"),
    ("10538102", "Cedar Valley Christian School 33128165 Keokuk Christian Academy"),
    ("27098501", "Central Iowa Christian School 09998104 Kuemper Catholic Grade School"),
    ("06098204", "Central Lutheran School 09998101 Kuemper High School"),
    ("17378117", "Christ The King School 69618148 La Salle Catholic School"),
    ("11978202", "Clarinda Lutheran School Association 10538117 LaSalle Catholic Elementary School"),
    ("24038103", "Clear Lake Classical - Ventura Campus 10538217 LaSalle Catholic Middle School"),
    ("12338102", "Clear Lake Classical School 31058121 Liberty Christian School"),
    ("67958114", "Columbus Catholic High School 11168106 Lighthouse Christian Academy"),
    ("23138301", "Community Christian School 70298204 Lutheran Interparish School"),
    ("67628203", "Community Lutheran School 21698502 Maharishi School"),
    ("06218121", "Coram Deo Academy 47978121 Main Street School"),
    ("33758103", "Cornerstone Christian School 05858107 Marquette Catholic Elementary"),
    ("40338103", "Danbury Catholic School 05858109 Marquette Catholic High School"),
    ("17378134", "Des Moines Adventist School 41048105 Marshalltown Christian School"),
    ("65798502", "Des Moines Christian Elementary School 60398115 Mater Dei School Immaculate Conception Center"),
    ("65798503", "Des Moines Christian Secondary 60398116 Mater Dei School Nativity Center"),
    ("67958210", "Diamond Star Academy Waterloo 15038105 Mayflower Heritage Christian School"),
    ("67958115", "Don Bosco High School 18638128 Mazzuchelli Catholic Middle School"),
    ("69578103", "Dowling Catholic High School 31418121 Montessori School of Iowa City"),
    ("18638170", "Dubuque Dream Center Academy 37158101 Montessori School of Marion"),
    ("31418155", "Ehsan Islamic School 06218106 Morning Star Academy"),
    ("20888102", "Emmetsburg Catholic School 45368101 Mount Pleasant Christian School"),
    ("31418103", "Faith Academy 17378221 Mt Olive Lutheran School"),
    ("36008105", "Gehlen Catholic Elem School 45818121 Muscatine Adventist Christian School"),
    ("36008104", "Gehlen Catholic High School 45818165 Muscatine Christian Academy"),
    ("32318121", "Gospel Assembly Christian Academy 56078319 Netherlands Reformed Christian School"),
    ("58058109", "Grand View Christian Elementary 46178101 Nevada Seventh-Day Adventist School"),
    ("17378504", "Grand View Christian High School 06218125 New City Classical Academy"),
    ("17378507", "Grand View Christian Middle School 41318102 Newman Catholic Elementary School"),
    ("08828106", "Great River Christian School 41318105 Newman Catholic High School"),
    ("36458100", "Heartland Christian School 47258301 Newton Christian Day School"),
    ("31418106", "Heritage Christian School 41318401 North Iowa Christian School"),
    ("31418157", "Hidaya Academy 16388106 Northeast Iowa Montessori School"),
    ("31418167", "Hillside Christian School 10958505 Northwest Iowa Protestant Reformed School"),
    ("60398104", "Holy Cross Blessed Sacrament School 08828104 Notre Dame Elementary School Burlington"),
    ("60398114", "Holy Cross St Michael School 30298104 Notre Dame Elementary School Cresco"),
    ("17378108", "Holy Family School 08828101 Notre Dame High School Burlington"),
    ("23228602", "Holy Trinity Elem School - Ft Madison 14768109 One School Global - Council Bluffs"),
    ("23228105", "Holy Trinity Jr-Sr High School - Ft Madison 17378120 One School Global - Des Moines"),
    ("17378119", "Holy Trinity School - Des Moines 41498308 Orange City Christian School"),
    ("12118105", "HomeGrown Christian Learning Center 50138301 Oskaloosa Christian School"),
    ("07478305", "Hull Christian School 50498301 Ottumwa Christian School"),
    ("07478306", "Hull Protestant Reformed Christian School 18638126 Our Lady of Guadalupe"),
    ("10538213", "ICCR Academy 42718106 Pathway Christian School"),
    ("67958110", "Immaculate Conception - Gilbertville 51668301 Pella Christian Grade School"),
    ("11168102", "Immaculate Conception School - Charles City 51668302 Pella Christian High School"),
    ("69838303", "Inwood Christian School 51668305 Peoria Christian School"),
    ("31418123", "Iowa Conservatory 52838102 Pocahontas Catholic Grade School"),
    ("61028102", "Iowa Great Lakes Lutheran School 12788110 Prince of Peace Catholic High School"),
    ("42718506", "Iowa Mennonite School dba Hillcrest Academy 12788103 Prince of Peace Catholic Elementary"),
    ("47978115", "Providence Christian School 01358102 St Patrick School Waukon"),
    ("31418108", "Regina Elementary School 59498101 St Patrick's School Sheldon"),
    ("31418104", "Regina Jr Sr High School 23138206 St Paul Lutheran School - Ft Dodge"),
    ("10538216", "Regis Middle School 16118109 St Paul The Apostle School Davenport"),
    ("18638136", "Resurrection Elementary 09168201 St Pauls Lutheran School Latimer"),
    ("06218110", "Rivermont Collegiate 60398217 St Pauls Lutheran School - Sioux City"),
    ("56078315", "Rock Valley Christian School 68408207 St Pauls Lutheran School Waverly"),
    ("67958401", "Royal Legacy Christian Academy 65798112 St Pius X Catholic School Urbandale"),
    ("61028101", "Sacred Heart Catholic School - Spencer 10538116 St Pius X School - Cedar Rapids"),
    ("44468106", "Sacred Heart Grade School - Monticello 17018102 St Rose Of Lima School"),
    ("07298103", "Sacred Heart School - Boone 61008105 St Teresa of Calcutta School Ossian"),
    ("40418108", "Sacred Heart School - Maquoketa 61008101 St Teresa of Calcutta School Spillville"),
    ("60398111", "Sacred Heart School - Sioux City 17378113 St Theresa School"),
    ("69578104", "Sacred Heart School - West Des Moines 68678102 St Thomas Aquinas School"),
    ("14768108", "Saint Albert School 31148102 Strong Roots Christian School"),
    ("67958105", "Saint Edward Elementary School 39068303 Sully Christian School"),
    ("52508101", "Saint Joan of Arc 10538200 Summit Schools Inc"),
    ("45818103", "Saints Mary and Mathias Catholic School 60988107 Tama Toledo Christian School"),
    ("28628304", "Sanborn Christian School 31418165 Tamarack Discovery School"),
    ("69308503", "Scattergood Friends School 41498312 The Classical Academy of Sioux Center"),
    ("69618153", "Seton Catholic Elem School Farley Center 58058105 The Conservatory of Worship Arts"),
    ("69618157", "Seton Catholic Elem School Peosta Center 12788130 The Lighthouse Schools"),
    ("50498101", "Seton Catholic School - Ottumwa 00098302 Timothy Christian School"),
    ("01268101", "Seton Grade School - Algona 65098109 Trinity Catholic School Protivin"),
    ("28268101", "Shelby Co. Catholic Sch 36918101 Trinity Christian Academy"),
    ("59498305", "Sheldon Christian School 07478109 Trinity Christian High School"),
    ("60308314", "Sioux Center Christian School 07298204 Trinity Lutheran School Boone"),
    ("35558101", "Siouxland Christian Secondary School 10538214 Trinity Lutheran School - Cedar Rapids"),
    ("60398103", "Siouxland Community Christian School 16118212 Trinity Lutheran School Davenport"),
    ("51638106", "Southeastern Christian School 18638165 Tri-State Christian School"),
    ("17378106", "St Anthony School 18638163 Tri-State Christian School"),
    ("32048104", "St Athanasius School 17378125 Two Rivers Classical Academy"),
    ("17378107", "St Augustin School 69578110 Two Rivers Classical Academy"),
    ("16388102", "St Benedict School 41498317 Unity Christian High School"),
    ("02258104", "St Cecilia School 17018201 Unity Ridge Lutheran School Denison"),
    ("18638122", "St Columbkille School 10448100 Valley Lutheran School"),
    ("23138104", "St Edmond Catholic 31148165 Victory Christian Academy"),
    ("41048103", "St Francis Catholic School 18638134 Wahlert Catholic High School"),
    ("68228101", "St Francis of Assisi School 68408155 Waverly Christian School"),
    ("69618103", "St Francis Xavier School 07478309 Western Christian High School"),
    ("67688103", "St James Elem School 31418102 Willowwind School"),
    ("31058105", "St John Elementary School 70568106 Winterset Christian Academy"),
    ("46628106", "St Joseph Community School - New Hampton 10538105 Xavier High School"),
    ("17378110", "St Joseph Elementary School - Des Moines 17378122 Xceed Oakmoor Academy"),
    ("10828109", "St Joseph School - De Witt 60998203 Zion-St. John Lutheran School Paullina"),
    ("40868106", "St Joseph School - Marion 6 DHS Program or Board of Regents School"),
    ("02618101", "St Luke the Evangelist Catholic School 31417015 Center for Disabilities and Development"),
    ("15038101", "St Malachy School 11529611 Cherokee Mental Health Institute"),
    ("30608101", "St Mary School - Humboldt 31059611 Independence Mental Health Institute"),
    ("62198102", "St Mary's Elementary - Storm Lake 36459610 Iowa School for the Deaf"),
    ("54868102", "St Mary's Grade School - RSM 20079601 State Training School"),
    ("54868103", "St Marys High School - Remsen 8 Out-of state"),
    ("62198101", "St Mary's High School - Storm Lake AL Alabama"),
    ("69508104", "St Marys School - Manchester AK Alaska"),
    ("10538109", "St Matthew School AZ Arizona"),
    ("02348102", "St Patrick School - Anamosa AR Arkansas"),
    ("10448113", "St Patrick School - Cedar Falls CA California"),
    ("51848102", "St Patrick School - Perry CZ Canal Zone"),
    ("17019601", "Denison Job Corps"),
    ("50499601", "Ottumwa Job Corps"),
    ("90999601", "Out-Of-State Job Corps"),
    ("81000101", "Choice Charter"),
    ("83000101", "Empowering Excellence Charter School"),
    ("84000101", "Great Oaks DSM"),
    ("27720175", "Hamburg Charter School"),
    ("82000101", "Horizon Science Academy DSM"),
    ("82250102", "Horizon Science Academy DAV"),
]

def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM organizations WHERE id::text = :sentinel"),
        {"sentinel": "CHAR(36)"},
    )

    rows = [{"name": name.strip(), "code": code.strip()} for code, name in organization_data]

    upsert = sa.text("""
        INSERT INTO organizations (name, code)
        VALUES (:name, :code)
        ON CONFLICT (code) DO UPDATE
        SET name = EXCLUDED.name,
            updated_at = NOW()
    """)

    # Let server_default(gen_random_uuid()) populate id automatically
    conn.execute(upsert, rows)

def downgrade() -> None:
    conn = op.get_bind()
    codes = [code for code, _ in organization_data]

    conn.execute(
        sa.text("DELETE FROM organizations WHERE code = ANY(:codes)"),
        {"codes": codes},
    )
