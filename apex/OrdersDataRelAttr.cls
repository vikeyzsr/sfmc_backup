public class OrderDataRA {
    public OrderDataRA() {}

    @AuraEnabled @InvocableVariable public String orderId;
    @AuraEnabled @InvocableVariable public Date orderDate;
    @AuraEnabled @InvocableVariable public Decimal orderPrice;

    @AuraEnabled @InvocableVariable public String productID;
    @AuraEnabled @InvocableVariable public String productName;
    @AuraEnabled @InvocableVariable public Decimal unitPrice;
}
