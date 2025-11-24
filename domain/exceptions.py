class DomainException(Exception):
    pass


class MerchantNotFoundError(DomainException):
    pass


class InsufficientFundsError(DomainException):
    pass


class InvalidTransferError(DomainException):
    pass


class DuplicateIdempotencyKeyError(DomainException):
    pass

