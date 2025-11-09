import os
from dataclasses import dataclass, field
import ctypes

# Sensible fallbacks when detection is unavailable (e.g. headless CI)
DEFAULT_SCREEN_WIDTH = 1920
DEFAULT_SCREEN_HEIGHT = 1080


def get_screen_size_safe():
    """Best-effort screen detection that works across desktop platforms."""
    width = height = None

    try:
        if os.name == 'nt':
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
        else:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
    except Exception as e:
        print(f"⚠️ Screen size detection failed: {e}")

    width = width or DEFAULT_SCREEN_WIDTH
    height = height or DEFAULT_SCREEN_HEIGHT
    return width, height


def get_scale_factor():
    """Return OS DPI scaling where possible."""
    try:
        if os.name == 'nt':
            ctypes.windll.user32.SetProcessDPIAware()
            user32 = ctypes.windll.user32
            dc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, dc)
            return round(dpi / 96.0, 2)
        else:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            scaling = root.tk.call('tk', 'scaling')
            root.destroy()
            return round(float(scaling), 2)
    except Exception as exc:
        print(f"⚠️ DPI detection failed: {exc}")
        return 1.0
    

_SCREEN_WIDTH, _SCREEN_HEIGHT = get_screen_size_safe()


@dataclass
class BrowserConfig:
    width: int = field(default_factory=lambda: _SCREEN_WIDTH)
    height: int = field(default_factory=lambda: _SCREEN_HEIGHT)
    headless: bool = not True
    device_scale_factor: float = field(default_factory=get_scale_factor)
    screenshot_dir: str = "screenshots"
    screenshot_format: str = "jpeg"
    screenshot_quality: int = 70



@dataclass
class AppConfig:
    base_url: str = "https://wmqa.subaru1.com/manh/index.html?i=102"
    change_warehouse: str = "LPM"
    timeout_default: int = 5000
    check_interval: int = 200
    post_message_text: str = """<?xml version="1.0"?>
<tXML>
  <Header>
    <Source>STARS</Source>
    <Action_Type>update</Action_Type>
    <Message_Type>DistributionOrder</Message_Type>
    <Company_ID>1</Company_ID>
  </Header>
  <Message>
    <DistributionOrder>
      <DistributionOrderType>Store Distributions</DistributionOrderType>
      <DistributionOrderId>9188 336201</DistributionOrderId>
      <OrderType>INTERNAL TRANSFER</OrderType>
      <OrderedDttm>08/02/2025 15:03</OrderedDttm>
      <OriginFacilityAliasId>L PM</OriginFacilityAliasId>
      <OriginAddressLine1>5190 S STATE ROAD 267</OriginAddressLine1>
      <OriginCity>LEBANON</OriginCity>
      <OriginCountry>US</OriginCountry>
      <OriginStateOrProvince>IN</OriginStateOrProvince>
      <OriginPostalCode>46052</OriginPostalCode>
      <DestinationAddressLine1>945 MONUMENT DRIVE, SUITE A</DestinationAddressLine1>
      <DestinationCity>LEBANON</DestinationCity>
      <DestinationCounty>BOONE</DestinationCounty>
      <DestinationCountry>US</DestinationCountry>
      <DestinationStateOrProvince>IN</DestinationStateOrProvince>
      <DestinationPostalCode>46052</DestinationPostalCode>
      <PickupStartDttm>08/13/2025 23:59</PickupStartDttm>
      <PickupEndDttm>08/13/2025 23:59</PickupEndDttm>
      <DeliveryStartDttm>08/13/2025 23:59</DeliveryStartDttm>
      <DeliveryEndDttm>08/13/2025 23:59</DeliveryEndDttm>
      <LpnCubingIndicator>51</LpnCubingIndicator>
      <MajorOrderGroupAttribute>001900-334202</MajorOrderGroupAttribute>
      <DsgShipVia>GRDH</DsgShipVia>
      <FederatedStoreNbr>001900</FederatedStoreNbr>
      <SalesOrderNbr>9499914</SalesOrderNbr>
      <DistroNumber>91883362</DistroNumber>
      <DestinationContactName>334202</DestinationContactName>
      <BillToName>001900-134739</BillToName>
      <DestinationFacilityAliasId>001900-334202</DestinationFacilityAliasId>
      <ReferenceField6>LPM</ReferenceField6>
      <ReferenceNumberField1>1</ReferenceNumberField1>
      <RefShipmentNbr>001900334202</RefShipmentNbr>
      <RefShipmentStopSeqNbr>1</RefShipmentStopSeqNbr>
      <ReferenceField1>LEB</ReferenceField1>
      <ContentLabelType>001</ContentLabelType>
      <NbrOfContentLabelsToPrint>1</NbrOfContentLabelsToPrint>
      <FullProfileName>DFT ORD PROFILE</FullProfileName>
      <ReferenceField3>LPMSHIP</ReferenceField3>
      <CustomFieldList>
        <CustomField>
          <Name>OrderCreationDate</Name>
          <Value>08/01/2025 17:19</Value>
        </CustomField>
        <CustomField>
          <Name>NumberOfLines</Name>
          <Value>1</Value>
        </CustomField>
        <CustomField>
          <Name>OrderingSource</Name>
          <Value>Internal</Value>
        </CustomField>
      </CustomFieldList>
      <LineItem>
        <DoLineNbr>196499960</DoLineNbr>
        <ItemName>64661AN06AVH</ItemName>
        <Description>BELT ASSY R OUT  UWR</Description>
        <Length>12.5</Length>
        <Width>8.7</Width>
        <Height>5</Height>
        <TotalMonetaryValue>43.4</TotalMonetaryValue>
        <MonetaryValueCurrencyCode>USD</MonetaryValueCurrencyCode>
        <PurchaseOrderNbr>9499914</PurchaseOrderNbr>
        <PurchaseOrderLineNbr>196499960</PurchaseOrderLineNbr>
        <ExternalSystemPurchaseOrderNbr>9499914</ExternalSystemPurchaseOrderNbr>
        <ExternalSystemPoLineNbr>1.1</ExternalSystemPoLineNbr>
        <ReferenceField1>005</ReferenceField1>
        <ReferenceField2>002</ReferenceField2>
        <CustomFieldList/>
        <Quantity>
          <OrderQty>7</OrderQty>
          <QtyUOM>Unit</QtyUOM>
        </Quantity>
      </LineItem>
    </DistributionOrder>
  </Message>
</tXML>"""


class Settings:
    browser = BrowserConfig()
    app = AppConfig()

    print(f"Detected screen: {browser.width}x{browser.height}, scale={browser.device_scale_factor}")

    @classmethod
    def from_env(cls):
        """Load settings from environment variables"""
        cls.app.base_url = os.getenv("APP_URL", cls.app.base_url)
        cls.app.change_warehouse = os.getenv("DEFAULT_WAREHOUSE", cls.app.change_warehouse)
        cls.app.post_message_text = os.getenv("POST_MESSAGE_TEXT", cls.app.post_message_text)
        return cls
