package org.knowm.xchange.bot;

import java.io.IOException;

import org.knowm.xchange.Exchange;
import org.knowm.xchange.ExchangeFactory;
import org.knowm.xchange.bittrex.v1.BittrexExchange;
import org.knowm.xchange.bittrex.v1.dto.marketdata.BittrexTicker;
import org.knowm.xchange.bittrex.v1.service.BittrexMarketDataServiceRaw;
import org.knowm.xchange.currency.Currency;
import org.knowm.xchange.currency.CurrencyPair;
import org.knowm.xchange.dto.marketdata.Ticker;
import org.knowm.xchange.service.marketdata.MarketDataService;

/**
 * Demonstrate requesting Ticker at Bitstamp. You can access both the raw data from Bitstamp or the XChange generic DTO data format.
 */
public class BittrexTickerDemo {

  public static void main(String[] args) throws IOException {

    // Use the factory to get Bitstamp exchange API using default settings
    Exchange bittrex = ExchangeFactory.INSTANCE.createExchange(BittrexExchange.class.getName());

    // Interested in the public market data feed (no authentication)
    MarketDataService marketDataService = bittrex.getMarketDataService();

    generic(marketDataService);
    //raw((BittrexMarketDataServiceRaw) marketDataService);
  }

  private static void generic(MarketDataService marketDataService) throws IOException {

    Ticker ticker = marketDataService.getTicker(new CurrencyPair("XRP", "BTC"));

    System.out.println(ticker.toString());
  }

  private static void raw(BittrexMarketDataServiceRaw marketDataService) throws IOException {

    BittrexTicker bitstampTicker = marketDataService.getBittrexTicker("BTC-DOGE");

    System.out.println(bitstampTicker.toString());
  }

}
